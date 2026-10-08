"""서비스 계층: 모든 업무 로직. 라우터(FastAPI)는 이 함수들을 부르기만 해요.

`db` 는 dbapi.Db (SQLAlchemy 든 sqlite3 든 같은 SQL 실행). 그래서 이 파일 전체를 sqlite3 로 테스트할 수 있어요.
오류는 ServiceError(상태코드, 메시지)로 올리고, 라우터가 HTTPException 으로 바꿔요.
쓰기 작업은 "시도 → 검증 → 커밋, 실패하면 롤백" 순서라서 거래가 반만 저장되는 일이 없어요.
"""
from datetime import date, datetime, timedelta

from . import sql
from .ledger import LedgerError, replay
from .strategy import ENTRY_TYPES, FEE_RATE, describe_rule, signal_sql, simulate, summarize

PERIODS = {"6m": 183, "1y": 365, "all": None}


class ServiceError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def _num(v, name, lo, hi, integer=False):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ServiceError(422, f"{name}은(는) 숫자로 입력해 주세요.")
    if not (lo <= x <= hi):
        raise ServiceError(422, f"{name}은(는) {lo:g} ~ {hi:g} 사이로 입력해 주세요.")
    if integer and x != int(x):
        raise ServiceError(422, f"{name}은(는) 정수로 입력해 주세요.")
    return int(x) if integer else x


# ───────────────────────── 종목·시세 ─────────────────────────
def list_companies(db, q: str = "") -> list:
    rows = db.all(sql.COMPANIES, like=f"%{q.strip()}%")
    latest = {r["company_id"]: r for r in db.all(sql.LATEST_ALL)}
    for r in rows:
        last = latest.get(r["company_id"])
        r["price"] = last["close"] if last else None
        r["trade_date"] = last["trade_date"] if last else None
        r["change_rate"] = round((last["close"] / last["prev_close"] - 1) * 100, 2) if last and last["prev_close"] else 0.0
    return rows


def get_company(db, code: str) -> dict:
    c = db.one(sql.COMPANY_BY_CODE, code=code)
    if not c:
        raise ServiceError(404, "종목을 찾을 수 없어요.")
    return c


def company_detail(db, code: str) -> dict:
    c = get_company(db, code)
    return next(x for x in list_companies(db) if x["code"] == c["code"])


def prices(db, code: str, days: int = 365) -> list:
    c = get_company(db, code)
    last = db.one(sql.LATEST_DATE, cid=c["company_id"])["d"]
    if not last:
        return []
    since = (date.fromisoformat(last[:10]) - timedelta(days=days)).isoformat()
    return db.all(sql.SERIES, cid=c["company_id"], since=since)


# ───────────────────────── 규칙 CRUD ─────────────────────────
def validate_rule(d: dict) -> dict:
    name = str(d.get("name") or "").strip()
    if not 1 <= len(name) <= 60:
        raise ServiceError(422, "규칙 이름은 1~60자로 입력해 주세요.")
    et = d.get("entry_type")
    if et not in ENTRY_TYPES:
        raise ServiceError(422, "진입 조건을 골라 주세요.")
    if et == "dip_buy":
        param = _num(d.get("entry_param"), "하락률(%)", 1, 30)
    else:
        param = _num(d.get("entry_param"), "기간(일)", 2, 250, integer=True)
    return {
        "name": name, "entry_type": et, "entry_param": param,
        "take_profit_pct": _num(d.get("take_profit_pct"), "익절(%)", 0.5, 200),
        "stop_loss_pct": _num(d.get("stop_loss_pct"), "손절(%)", 0.5, 50),
        "max_hold_days": _num(d.get("max_hold_days"), "최대 보유일", 1, 250, integer=True),
    }


def _with_text(r: dict) -> dict:
    return {**r, "text": describe_rule(r), "entry_label": ENTRY_TYPES[r["entry_type"]]}


def list_rules(db, client: str) -> list:
    return [_with_text(r) for r in db.all(sql.RULE_LIST, client=client)]


def get_rule(db, client: str, rid: int) -> dict:
    r = db.one(sql.RULE_GET, id=rid, client=client)
    if not r:
        raise ServiceError(404, "규칙을 찾을 수 없어요.")
    return r


def rule_detail(db, client: str, rid: int) -> dict:
    return next(r for r in list_rules(db, client) if r["rule_id"] == get_rule(db, client, rid)["rule_id"])


def create_rule(db, client: str, data: dict) -> dict:
    v = validate_rule(data)
    if db.one(sql.RULE_NAME_TAKEN, client=client, name=v["name"]):
        raise ServiceError(409, "같은 이름의 규칙이 이미 있어요.")
    rid = db.insert(sql.RULE_INSERT, client=client, now=_now(), **v)
    db.commit()
    return rule_detail(db, client, rid)


def update_rule(db, client: str, rid: int, data: dict) -> dict:
    cur = get_rule(db, client, rid)
    v = validate_rule({**cur, **{k: x for k, x in data.items() if x is not None}})
    taken = db.one(sql.RULE_NAME_TAKEN, client=client, name=v["name"])
    if taken and taken["rule_id"] != rid:
        raise ServiceError(409, "같은 이름의 규칙이 이미 있어요.")
    db.run(sql.RULE_UPDATE, id=rid, client=client, now=_now(), **v)
    db.commit()
    return rule_detail(db, client, rid)


def delete_rule(db, client: str, rid: int) -> None:
    get_rule(db, client, rid)
    db.run(sql.RULE_DELETE, id=rid, client=client)  # 백테스트는 CASCADE 로 같이 지워지고, 거래의 rule_id 는 NULL 로 바뀌어요
    db.commit()


# ───────────────────────── 신호 ─────────────────────────
def rule_signals(db, client: str, rid: int) -> list:
    """이 규칙의 진입 조건이 '가장 최근 거래일'에 맞은 종목들."""
    r = get_rule(db, client, rid)
    hits = {h["company_id"]: h["trade_date"] for h in db.all(signal_sql(r["entry_type"], r["entry_param"], single=False, latest_only=True))}
    return [{"code": c["code"], "name": c["name"], "price": c["price"], "change_rate": c["change_rate"], "signal_date": hits[c["company_id"]]}
            for c in list_companies(db) if c["company_id"] in hits]


def all_signals(db, client: str) -> list:
    out = []
    for r in db.all(sql.RULE_LIST, client=client):
        hits = rule_signals(db, client, r["rule_id"])
        if hits:
            out.append({"rule_id": r["rule_id"], "rule_name": r["name"], "rule_text": describe_rule(r), "companies": hits})
    return out


# ───────────────────────── 백테스트 ─────────────────────────
def _series_for(db, cid: int, period: str):
    if period not in PERIODS:
        raise ServiceError(422, "기간은 6m, 1y, all 중 하나예요.")
    last = db.one(sql.LATEST_DATE, cid=cid)["d"]
    first = db.one(sql.FIRST_DATE, cid=cid)["d"]
    if not last:
        raise ServiceError(422, "이 종목의 시세가 아직 없어요.")
    days = PERIODS[period]
    start = first[:10] if days is None else max(first[:10], (date.fromisoformat(last[:10]) - timedelta(days=days)).isoformat())
    series = db.all(sql.SERIES, cid=cid, since=start)
    if len(series) < 30:
        raise ServiceError(422, "시세가 30일보다 적어서 백테스트를 할 수 없어요.")
    return start, series


def run_backtest(db, client: str, rid: int, code: str, period: str = "1y") -> dict:
    rule = get_rule(db, client, rid)
    comp = get_company(db, code)
    start, series = _series_for(db, comp["company_id"], period)
    # 이동평균이 첫날부터 채워지도록 신호는 전체 기간에서 구하고, 매매는 시작일 이후만 해요.
    signals = [h["trade_date"][:10] for h in db.all(signal_sql(rule["entry_type"], rule["entry_param"], single=True), cid=comp["company_id"])]
    trades = simulate(series, signals, rule["take_profit_pct"], rule["stop_loss_pct"], rule["max_hold_days"], FEE_RATE, start=start)
    s = summarize(trades, series)
    try:
        run_id = db.insert(sql.RUN_INSERT, rule_id=rid, company_id=comp["company_id"], rule_text=describe_rule(rule), start_date=start,
                           end_date=series[-1]["d"], trade_count=s["trade_count"], win_count=s["win_count"], avg_return=s["avg_return"],
                           total_return=s["total_return"], mdd=s["mdd"], benchmark_return=s["benchmark_return"],
                           avg_hold_days=s["avg_hold_days"], now=_now())
        for t in trades:
            db.run(sql.BT_TRADE_INSERT, run_id=run_id, **t)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_run(db, client, run_id)


def list_runs(db, client: str, rid: int) -> list:
    get_rule(db, client, rid)
    return db.all(sql.RUN_LIST, rid=rid)


def get_run(db, client: str, run_id: int) -> dict:
    r = db.one(sql.RUN_GET, id=run_id, client=client)
    if not r:
        raise ServiceError(404, "백테스트 기록을 찾을 수 없어요.")
    trades = db.all(sql.RUN_TRADES, id=run_id)
    r["win_rate"] = round(r["win_count"] / r["trade_count"] * 100, 1) if r["trade_count"] else None
    return {**r, "trades": trades}


def delete_run(db, client: str, run_id: int) -> None:
    get_run(db, client, run_id)
    db.run(sql.RUN_DELETE, id=run_id, client=client)
    db.commit()


def rule_report(db, client: str, rid: int) -> dict:
    """백테스트(과거 시뮬레이션) 성적 vs 실제 모의투자(이 규칙으로 한 거래) 성적."""
    rule = rule_detail(db, client, rid)
    bt = db.one(sql.BACKTEST_AGG, rid=rid)
    n = bt["n"] or 0
    realized = []
    for a in db.all(sql.ACCOUNT_LIST, client=client):
        led = replay(db.all(sql.TRADES_RAW, aid=a["account_id"]), a["initial_cash"])
        realized += [x for x in led["realized"] if x["rule_id"] == rid]
    m = len(realized)
    w = sum(1 for x in realized if x["pnl"] > 0)
    return {
        "rule": rule,
        "backtest": {"companies": db.one(sql.BACKTEST_RUNS_USED, rid=rid)["n"], "trade_count": n, "win_rate": round((bt["wins"] or 0) / n * 100, 1) if n else None,
                     "avg_return": round(bt["avg_return"], 2) if n else None},
        "actual": {"trade_count": m, "win_rate": round(w / m * 100, 1) if m else None,
                   "avg_return": round(sum(x["return_pct"] for x in realized) / m, 2) if m else None, "total_pnl": round(sum(x["pnl"] for x in realized))},
    }


# ───────────────────────── 계좌·거래 ─────────────────────────
def list_accounts(db, client: str) -> list:
    return db.all(sql.ACCOUNT_LIST, client=client)


def _account(db, client: str, aid: int) -> dict:
    a = db.one(sql.ACCOUNT_GET, id=aid, client=client)
    if not a:
        raise ServiceError(404, "계좌를 찾을 수 없어요.")
    return a


def _account_name(v) -> str:
    name = str(v or "").strip()
    if not 1 <= len(name) <= 40:
        raise ServiceError(422, "계좌 이름은 1~40자로 입력해 주세요.")
    return name


def create_account(db, client: str, name, initial_cash) -> dict:
    name = _account_name(name)
    cash = _num(initial_cash, "시작 금액", 100_000, 10_000_000_000, integer=True)
    if db.one(sql.ACCOUNT_NAME_TAKEN, client=client, name=name):
        raise ServiceError(409, "같은 이름의 계좌가 이미 있어요.")
    aid = db.insert(sql.ACCOUNT_INSERT, client=client, name=name, cash=cash, now=_now())
    db.commit()
    return account_detail(db, client, aid)


def rename_account(db, client: str, aid: int, name) -> dict:
    _account(db, client, aid)
    name = _account_name(name)
    taken = db.one(sql.ACCOUNT_NAME_TAKEN, client=client, name=name)
    if taken and taken["account_id"] != aid:
        raise ServiceError(409, "같은 이름의 계좌가 이미 있어요.")
    db.run(sql.ACCOUNT_RENAME, id=aid, client=client, name=name)
    db.commit()
    return account_detail(db, client, aid)


def delete_account(db, client: str, aid: int) -> None:
    _account(db, client, aid)
    db.run(sql.ACCOUNT_DELETE, id=aid, client=client)  # 거래는 CASCADE 로 같이 지워져요
    db.commit()


def account_detail(db, client: str, aid: int) -> dict:
    a = _account(db, client, aid)
    led = replay(db.all(sql.TRADES_RAW, aid=aid), a["initial_cash"])
    quotes = {q["company_id"]: q for q in db.all(sql.LATEST_ALL)}
    names = {c["company_id"]: c for c in db.all(sql.COMPANIES, like="%")}
    holdings, stock_value = [], 0.0
    for cid, h in led["holdings"].items():
        price = quotes[cid]["close"]
        value = price * h["qty"]
        stock_value += value
        holdings.append({"code": names[cid]["code"], "name": names[cid]["name"], "qty": h["qty"], "avg_cost": h["avg_cost"], "price": price,
                         "value": round(value), "pnl": round(value - h["cost"]), "pnl_pct": round((value / h["cost"] - 1) * 100, 2)})
    equity = a["cash"] + stock_value
    for h in holdings:
        h["weight"] = round(h["value"] / equity * 100, 1) if equity else 0
    holdings.sort(key=lambda h: -h["value"])
    # 감사: DB 에 저장된 현금 = 거래로 다시 계산한 현금 / SQL 로 센 보유 수량 = 장부 재계산 수량
    au = db.one(sql.AUDIT_CASH, aid=aid)
    sql_qty = {r["company_id"]: int(r["qty"]) for r in db.all(sql.HOLDINGS_SQL, aid=aid)}
    audit = {"cash_ok": abs(au["cash"] - au["expected"]) < 0.01, "holdings_ok": sql_qty == {c: h["qty"] for c, h in led["holdings"].items()}}
    realized = round(sum(r["pnl"] for r in led["realized"]))
    return {**a, "stock_value": round(stock_value), "equity": round(equity), "pnl": round(equity - a["initial_cash"]),
            "pnl_pct": round((equity / a["initial_cash"] - 1) * 100, 2), "realized_pnl": realized, "holdings": holdings, "audit": audit}


def list_trades(db, client: str, aid: int) -> list:
    _account(db, client, aid)
    return db.all(sql.TRADES_VIEW, aid=aid)


def _check_rule(db, client, rule_id):
    if rule_id in (None, ""):
        return None
    get_rule(db, client, int(rule_id))  # 남의 규칙이면 404
    return int(rule_id)


def _commit_if_valid(db, a: dict, aid: int, fail_message: str):
    """거래를 넣거나 지운 상태에서 장부 전체를 다시 계산해 보고, 문제가 없을 때만 현금을 갱신·커밋해요."""
    try:
        led = replay(db.all(sql.TRADES_RAW, aid=aid), a["initial_cash"])
    except LedgerError as e:
        db.rollback()
        raise ServiceError(409, f"{fail_message} {e}")
    db.run(sql.ACCOUNT_SET_CASH, id=aid, cash=led["cash"])
    db.commit()


def create_trade(db, client: str, aid: int, data: dict) -> dict:
    a = _account(db, client, aid)
    side = data.get("side")
    if side not in ("buy", "sell"):
        raise ServiceError(422, "매수/매도를 골라 주세요.")
    qty = _num(data.get("qty"), "수량", 1, 10_000_000, integer=True)
    comp = get_company(db, str(data.get("code") or ""))
    d = str(data.get("trade_date") or "")[:10]
    try:
        date.fromisoformat(d)
    except ValueError:
        raise ServiceError(422, "날짜 형식이 올바르지 않아요.")
    px = db.one(sql.PRICE_ON, cid=comp["company_id"], d=d)
    if not px:
        raise ServiceError(422, f"{d} 은(는) 거래일이 아니거나 시세가 없어요.")
    price = float(px["close"])
    rule_id = _check_rule(db, client, data.get("rule_id"))
    fee = round(price * qty * FEE_RATE, 2)
    memo = str(data.get("memo") or "")[:200]
    try:
        tid = db.insert(sql.TRADE_INSERT, account_id=aid, company_id=comp["company_id"], rule_id=rule_id, side=side, trade_date=d,
                        price=price, qty=qty, fee=fee, memo=memo)
    except Exception:
        db.rollback()
        raise
    _commit_if_valid(db, a, aid, "거래를 할 수 없어요.")
    return db.one(sql.TRADE_ONE, tid=tid, aid=aid)


def update_trade(db, client: str, aid: int, tid: int, data: dict) -> dict:
    _account(db, client, aid)
    cur = db.one(sql.TRADE_ONE, tid=tid, aid=aid)
    if not cur:
        raise ServiceError(404, "거래를 찾을 수 없어요.")
    # 가격·수량·날짜는 장부가 흔들리지 않도록 고칠 수 없고, 메모와 '어떤 규칙에 따른 거래인지'만 바꿀 수 있어요.
    memo = str(data["memo"])[:200] if data.get("memo") is not None else cur["memo"]
    rule_id = _check_rule(db, client, data["rule_id"]) if "rule_id" in data else cur["rule_id"]
    db.run(sql.TRADE_UPDATE, tid=tid, aid=aid, memo=memo, rule_id=rule_id)
    db.commit()
    return db.one(sql.TRADE_ONE, tid=tid, aid=aid)


def delete_trade(db, client: str, aid: int, tid: int) -> None:
    a = _account(db, client, aid)
    if not db.one(sql.TRADE_ONE, tid=tid, aid=aid):
        raise ServiceError(404, "거래를 찾을 수 없어요.")
    db.run(sql.TRADE_DELETE, tid=tid, aid=aid)
    _commit_if_valid(db, a, aid, "이 거래를 지우면 이후 거래가 맞지 않아요.")


def my_trades_for_company(db, client: str, code: str) -> list:
    c = get_company(db, code)
    return db.all(sql.MY_TRADES_FOR_COMPANY, client=client, cid=c["company_id"])


# ───────────────────────── 시스템 ─────────────────────────
def status(db) -> dict:
    counts = {t: db.one(f"SELECT COUNT(*) AS n FROM {t}")["n"] for t in ("company", "price_daily", "rule", "backtest_run", "account", "trade")}  # 고정된 표 이름만
    sample = db.one(sql.HAS_SAMPLE)["n"] > 0
    logs = db.all("SELECT job, source, status, row_count, message, finished_at FROM ingestion_log ORDER BY log_id DESC LIMIT 6")
    return {"source": "sample" if sample else ("pykrx" if counts["price_daily"] else "empty"), "is_sample": sample,
            "last_price_date": db.one("SELECT MAX(trade_date) AS d FROM price_daily")["d"], "counts": counts, "logs": logs}


# ───────────────────────── 대시보드 ─────────────────────────
def dashboard(db) -> dict:
    from .scoring import score_rows

    rows = score_rows(db.all(sql.DASH_ROWS))
    for r in rows:
        r["trade_date"] = r["trade_date"][:10]
    up = sum(1 for r in rows if (r["chg"] or 0) > 0)
    down = sum(1 for r in rows if (r["chg"] or 0) < 0)
    r3 = [r["r3m"] for r in rows if r["r3m"] is not None]
    summary = {"count": len(rows), "up": up, "down": down, "flat": len(rows) - up - down,
               "last_date": max((r["trade_date"] for r in rows), default=None), "avg_r3m": round(sum(r3) / len(r3), 2) if r3 else None}
    return {"summary": summary, "sectors": db.all(sql.SECTOR_AGG), "rows": rows}


def company_analysis(db, code: str) -> dict:
    """가격 흐름 숫자(수익률·120일선 괴리·최대 낙폭·변동성) + 투자지표 + 종합 점수 구성."""
    c = get_company(db, code)
    cid = c["company_id"]
    rows = dashboard(db)["rows"]
    dash = next((r for r in rows if r["code"] == code), None)
    if not dash:
        raise ServiceError(404, "이 종목의 시세가 아직 없어요.")
    today = date.fromisoformat(dash["trade_date"])
    year_ago = (today - timedelta(days=365)).isoformat()
    mdd = db.one(sql.ANALYSIS_MDD, cid=cid, since=year_ago)["mdd"]
    rets = [r["ret_pct"] for r in db.all(sql.DAILY_RETURNS, cid=cid, since=(today - timedelta(days=90)).isoformat())]
    vol_d = vol_a = None
    if len(rets) >= 20:
        m = sum(rets) / len(rets)
        sd = (sum((x - m) ** 2 for x in rets) / (len(rets) - 1)) ** 0.5
        vol_d, vol_a = round(sd, 2), round(sd * 252 ** 0.5, 1)
    rnd = lambda v, n=2: None if v is None else round(v, n)
    return {"code": code, "name": c["name"], "sector": dash["sector"], "trade_date": dash["trade_date"], "close": dash["close"], "volume": dash["volume"],
            "returns": {"1개월": rnd(dash["r1m"]), "3개월": rnd(dash["r3m"]), "6개월": rnd(dash["r6m"])}, "ma120_gap": rnd(dash["ma_gap"]),
            "vol_ratio": rnd(dash["vol_ratio"]), "mdd": rnd(mdd), "volatility_daily": vol_d, "volatility_annual": vol_a,
            "per": dash["per"], "pbr": dash["pbr"], "score": dash["score"], "score_parts": dash["score_parts"], "score_pool": len(rows)}


def company_fundamentals(db, code: str, days: int = 365) -> list:
    c = get_company(db, code)
    last = db.one("SELECT MAX(trade_date) AS d FROM fundamental_daily WHERE company_id = :cid", cid=c["company_id"])["d"]
    if not last:
        return []
    since = (date.fromisoformat(last[:10]) - timedelta(days=days)).isoformat()
    return db.all(sql.FUND_SERIES, cid=c["company_id"], since=since)


def company_financials(db, code: str, n: int = 5) -> list:
    return db.all(sql.FINANCIALS, cid=get_company(db, code)["company_id"], n=n)


def company_peers(db, code: str) -> list:
    return db.all(sql.PEERS, cid=get_company(db, code)["company_id"])


def company_monthly(db, code: str) -> list:
    return db.all(sql.MONTHLY, cid=get_company(db, code)["company_id"])
