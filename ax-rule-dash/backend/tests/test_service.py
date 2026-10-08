"""서비스 계층(규칙·백테스트·계좌·거래 장부)을 sqlite3 로 끝까지 검증해요. API 가 부르는 함수 그대로예요."""
import pytest

from app import service as S
from app import sql
from app.dbapi import lite_db
from app.ledger import LedgerError, replay
from app.strategy import FEE_RATE
from conftest import A, B

RULE = {"name": "20일선 돌파", "entry_type": "ma_cross", "entry_param": 20, "take_profit_pct": 8, "stop_loss_pct": 4, "max_hold_days": 20}


def close_on(db, code, d):
    c = S.get_company(db, code)
    return db.one(sql.PRICE_ON, cid=c["company_id"], d=d)["close"]


def two_dates(db, code="005930"):
    rows = S.prices(db, code, 30)
    return rows[3]["d"][:10], rows[10]["d"][:10], rows[-1]["d"][:10]


# ───── 규칙 ─────
def test_rule_crud_validation_and_privacy(db):
    r = S.create_rule(db, A, RULE)
    assert r["text"].startswith("종가가 20일선을 위로 뚫으면 매수") and r["run_count"] == 0
    with pytest.raises(S.ServiceError) as e:
        S.create_rule(db, A, RULE)
    assert e.value.status == 409  # 같은 이름 중복
    for bad in ({**RULE, "name": " "}, {**RULE, "entry_type": "x"}, {**RULE, "entry_param": 1}, {**RULE, "entry_param": 2.5},
                {**RULE, "take_profit_pct": 0}, {**RULE, "stop_loss_pct": 99}, {**RULE, "max_hold_days": 0}, {**RULE, "entry_param": "abc"}):
        with pytest.raises(S.ServiceError) as e:
            S.create_rule(db, A, {**bad, "name": bad["name"] or " "})
        assert e.value.status == 422
    up = S.update_rule(db, A, r["rule_id"], {"take_profit_pct": 12})
    assert up["take_profit_pct"] == 12 and up["name"] == "20일선 돌파"
    assert S.list_rules(db, B) == []
    for fn in (lambda: S.get_rule(db, B, r["rule_id"]), lambda: S.update_rule(db, B, r["rule_id"], {"name": "x"}), lambda: S.delete_rule(db, B, r["rule_id"])):
        with pytest.raises(S.ServiceError) as e:
            fn()
        assert e.value.status == 404
    S.delete_rule(db, A, r["rule_id"])
    assert S.list_rules(db, A) == []


def test_db_check_constraints_block_bad_rows(conn):
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO rule(client_id,name,entry_type,entry_param,take_profit_pct,stop_loss_pct,max_hold_days,created_at,updated_at) "
                     "VALUES ('a','n','magic',5,5,5,5,'2026-01-01','2026-01-01')")
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):  # 잔고는 음수가 될 수 없어요
        conn.execute("INSERT INTO account(client_id,name,initial_cash,cash,created_at) VALUES ('a','n',1000000,-1,'2026-01-01')")
    conn.rollback()


# ───── 백테스트 ─────
def test_run_backtest_persists_and_matches_manual_summary(db):
    r = S.create_rule(db, A, RULE)
    run = S.run_backtest(db, A, r["rule_id"], "005930", "1y")
    assert run["code"] == "005930" and run["trade_count"] == len(run["trades"]) > 0
    rets = [t["return_pct"] for t in run["trades"]]
    assert run["win_count"] == sum(1 for x in rets if x > 0)
    assert run["avg_return"] == pytest.approx(sum(rets) / len(rets), abs=0.01)
    assert all(t["exit_date"] >= t["entry_date"] for t in run["trades"])
    assert run["start_date"] >= S.prices(db, "005930", 400)[0]["d"]
    assert all(t["entry_date"] >= run["start_date"] for t in run["trades"])
    assert "20일선" in run["rule_text"] and S.list_runs(db, A, r["rule_id"])[0]["run_id"] == run["run_id"]
    # 규칙을 고쳐도 옛 결과의 설명은 그대로
    S.update_rule(db, A, r["rule_id"], {"entry_param": 10})
    assert "20일선" in S.get_run(db, A, run["run_id"])["rule_text"]
    # 6개월은 1년보다 거래가 같거나 적어요
    half = S.run_backtest(db, A, r["rule_id"], "005930", "6m")
    assert half["trade_count"] <= S.run_backtest(db, A, r["rule_id"], "005930", "all")["trade_count"]


def test_backtest_privacy_errors_and_cascade(conn, db):
    r = S.create_rule(db, A, RULE)
    run = S.run_backtest(db, A, r["rule_id"], "000660", "1y")
    for fn in (lambda: S.run_backtest(db, B, r["rule_id"], "000660"), lambda: S.get_run(db, B, run["run_id"]), lambda: S.delete_run(db, B, run["run_id"])):
        with pytest.raises(S.ServiceError) as e:
            fn()
        assert e.value.status == 404
    with pytest.raises(S.ServiceError) as e:
        S.run_backtest(db, A, r["rule_id"], "999999")
    assert e.value.status == 404
    with pytest.raises(S.ServiceError) as e:
        S.run_backtest(db, A, r["rule_id"], "000660", "5y")
    assert e.value.status == 422
    n = conn.execute("SELECT COUNT(*) FROM backtest_trade").fetchone()[0]
    assert n > 0
    S.delete_rule(db, A, r["rule_id"])  # 규칙을 지우면 실행 기록과 그 거래도 같이 사라져요(CASCADE)
    assert conn.execute("SELECT COUNT(*) FROM backtest_run").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM backtest_trade").fetchone()[0] == 0


def test_rule_signals_on_crafted_data(conn, db):
    """마지막 날 8% 급락하는 가짜 종목을 직접 넣어서 '오늘의 신호'가 잡히는지 확인."""
    conn.execute("INSERT INTO company(code,name,market,sector_id) VALUES ('999999','급락주','KOSPI',1)")
    cid = conn.execute("SELECT company_id FROM company WHERE code='999999'").fetchone()[0]
    days = [r["d"][:10] for r in S.prices(db, "005930", 40)]
    for i, d in enumerate(days):
        c = 1000 if i < len(days) - 1 else 920
        conn.execute("INSERT INTO price_daily(company_id,trade_date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,1)", (cid, d, c, c, c, c))
    conn.commit()
    r = S.create_rule(db, A, {**RULE, "name": "급락", "entry_type": "dip_buy", "entry_param": 5})
    hits = S.rule_signals(db, A, r["rule_id"])
    assert [h["code"] for h in hits] == ["999999"] and hits[0]["signal_date"] == days[-1]
    assert [x["rule_name"] for x in S.all_signals(db, A)] == ["급락"] and S.all_signals(db, B) == []


# ───── 장부 ─────
def test_ledger_replay_hand_calculated(conn):
    T = lambda i, side, d, p, q, fee=0: {"trade_id": i, "company_id": 1, "rule_id": None, "side": side, "trade_date": d, "price": p, "qty": q, "fee": fee}
    led = replay([T(1, "buy", "2026-01-02", 100, 10, 1), T(2, "buy", "2026-01-03", 200, 10, 2), T(3, "sell", "2026-01-04", 180, 5, 1)], 10_000)
    assert led["cash"] == 10_000 - 1001 - 2002 + 899  # = 7896
    # 평균단가 = (1001+2002)/20 = 150.15 → 5주 팔면 원가 750.75, 순매도 899 → 손익 148.25
    assert led["realized"][0]["pnl"] == pytest.approx(148.25, abs=0.01) and led["realized"][0]["avg_cost"] == pytest.approx(150.15, abs=0.01)
    assert led["holdings"][1]["qty"] == 15 and led["holdings"][1]["avg_cost"] == pytest.approx(150.15, abs=0.01)
    with pytest.raises(LedgerError):
        replay([T(1, "buy", "2026-01-02", 100, 10, 0)], 999)  # 현금 부족
    with pytest.raises(LedgerError):
        replay([T(1, "sell", "2026-01-02", 100, 1, 0)], 999)  # 없는 주식 매도


def test_buy_sell_cash_fee_and_audit(db):
    acc = S.create_account(db, A, "내 계좌", 10_000_000)
    d1, d2, _ = two_dates(db)
    buy = S.create_trade(db, A, acc["account_id"], {"code": "005930", "side": "buy", "trade_date": d1, "qty": 10})
    p1 = close_on(db, "005930", d1)
    assert buy["price"] == p1 and buy["fee"] == round(p1 * 10 * FEE_RATE, 2)  # 가격은 서버가 그날 종가로 채워요
    d = S.account_detail(db, A, acc["account_id"])
    assert d["cash"] == pytest.approx(10_000_000 - p1 * 10 - buy["fee"], abs=0.01)
    assert d["holdings"][0]["qty"] == 10 and d["audit"] == {"cash_ok": True, "holdings_ok": True}
    sell = S.create_trade(db, A, acc["account_id"], {"code": "005930", "side": "sell", "trade_date": d2, "qty": 4, "memo": "일부 정리"})
    p2 = close_on(db, "005930", d2)
    d = S.account_detail(db, A, acc["account_id"])
    assert d["holdings"][0]["qty"] == 6 and d["audit"]["cash_ok"] and d["audit"]["holdings_ok"]
    assert d["cash"] == pytest.approx(10_000_000 - p1 * 10 - buy["fee"] + p2 * 4 - sell["fee"], abs=0.01)
    avg = (p1 * 10 + buy["fee"]) / 10
    assert d["realized_pnl"] == round(p2 * 4 - sell["fee"] - avg * 4)
    assert d["equity"] == round(d["cash"] + d["stock_value"]) and d["pnl"] == d["equity"] - 10_000_000


def test_overdraft_and_oversell_are_rejected_and_not_saved(conn, db):
    acc = S.create_account(db, A, "작은 계좌", 100_000)
    d1, _, _ = two_dates(db)
    with pytest.raises(S.ServiceError) as e:
        S.create_trade(db, A, acc["account_id"], {"code": "000660", "side": "buy", "trade_date": d1, "qty": 100})  # 하이닉스 100주는 10만원으로 불가
    assert e.value.status == 409 and "모자라요" in e.value.message
    with pytest.raises(S.ServiceError) as e:
        S.create_trade(db, A, acc["account_id"], {"code": "005930", "side": "sell", "trade_date": d1, "qty": 1})
    assert e.value.status == 409 and "보유 수량" in e.value.message
    assert conn.execute("SELECT COUNT(*) FROM trade").fetchone()[0] == 0  # 실패한 시도는 흔적도 없어요
    assert S.account_detail(db, A, acc["account_id"])["cash"] == 100_000


def test_trade_input_validation(db):
    acc = S.create_account(db, A, "검증", 5_000_000)
    d1, _, _ = two_dates(db)
    for bad, status in (({"code": "005930", "side": "hold", "trade_date": d1, "qty": 1}, 422), ({"code": "005930", "side": "buy", "trade_date": d1, "qty": 0}, 422),
                        ({"code": "005930", "side": "buy", "trade_date": d1, "qty": 1.5}, 422), ({"code": "005930", "side": "buy", "trade_date": "2026-13-40", "qty": 1}, 422),
                        ({"code": "005930", "side": "buy", "trade_date": "2020-01-01", "qty": 1}, 422), ({"code": "000000", "side": "buy", "trade_date": d1, "qty": 1}, 404),
                        ({"code": "005930", "side": "buy", "trade_date": d1, "qty": 1, "rule_id": 999}, 404)):
        with pytest.raises(S.ServiceError) as e:
            S.create_trade(db, A, acc["account_id"], bad)
        assert e.value.status == status, bad


def test_delete_trade_keeps_ledger_consistent(conn, db):
    acc = S.create_account(db, A, "삭제검증", 10_000_000)
    aid = acc["account_id"]
    d1, d2, _ = two_dates(db)
    b = S.create_trade(db, A, aid, {"code": "005930", "side": "buy", "trade_date": d1, "qty": 10})
    s = S.create_trade(db, A, aid, {"code": "005930", "side": "sell", "trade_date": d2, "qty": 10})
    with pytest.raises(S.ServiceError) as e:  # 판 주식의 매수 기록을 지우면 매도가 말이 안 돼요
        S.delete_trade(db, A, aid, b["trade_id"])
    assert e.value.status == 409 and len(S.list_trades(db, A, aid)) == 2
    S.delete_trade(db, A, aid, s["trade_id"])  # 매도를 먼저 지우면 괜찮아요
    S.delete_trade(db, A, aid, b["trade_id"])
    d = S.account_detail(db, A, aid)
    assert d["cash"] == 10_000_000 and d["holdings"] == [] and d["audit"]["cash_ok"]


def test_account_privacy_unique_rename_cascade(conn, db):
    acc = S.create_account(db, A, "하나", 1_000_000)
    aid = acc["account_id"]
    with pytest.raises(S.ServiceError) as e:
        S.create_account(db, A, "하나", 1_000_000)
    assert e.value.status == 409
    assert S.create_account(db, B, "하나", 1_000_000)["account_id"] != aid  # 남은 같은 이름 가능
    for bad in (("", 1_000_000), ("x", 10), ("x", "abc")):
        with pytest.raises(S.ServiceError) as e:
            S.create_account(db, A, *bad)
        assert e.value.status == 422
    for fn in (lambda: S.account_detail(db, B, aid), lambda: S.list_trades(db, B, aid), lambda: S.delete_account(db, B, aid),
               lambda: S.create_trade(db, B, aid, {"code": "005930", "side": "buy", "trade_date": two_dates(db)[0], "qty": 1})):
        with pytest.raises(S.ServiceError) as e:
            fn()
        assert e.value.status == 404
    assert S.rename_account(db, A, aid, "새 이름")["name"] == "새 이름"
    S.create_trade(db, A, aid, {"code": "005930", "side": "buy", "trade_date": two_dates(db)[0], "qty": 1})
    S.delete_account(db, A, aid)
    assert conn.execute("SELECT COUNT(*) FROM trade").fetchone()[0] == 0  # 계좌를 지우면 거래도 같이(CASCADE)


def test_update_trade_only_memo_and_rule_and_rule_delete_sets_null(conn, db):
    acc = S.create_account(db, A, "메모", 10_000_000)
    aid = acc["account_id"]
    rule = S.create_rule(db, A, RULE)
    t = S.create_trade(db, A, aid, {"code": "005930", "side": "buy", "trade_date": two_dates(db)[0], "qty": 2, "rule_id": rule["rule_id"]})
    assert t["rule_name"] == "20일선 돌파"
    up = S.update_trade(db, A, aid, t["trade_id"], {"memo": "첫 매수", "price": 1, "qty": 999})  # 가격·수량은 무시돼요
    assert up["memo"] == "첫 매수" and up["price"] == t["price"] and up["qty"] == 2
    S.delete_rule(db, A, rule["rule_id"])
    assert S.list_trades(db, A, aid)[0]["rule_id"] is None  # ON DELETE SET NULL
    assert S.update_trade(db, A, aid, t["trade_id"], {"rule_id": None})["rule_id"] is None


def test_rule_report_backtest_vs_actual(db):
    rule = S.create_rule(db, A, RULE)
    rid = rule["rule_id"]
    S.run_backtest(db, A, rid, "005930", "1y")
    S.run_backtest(db, A, rid, "005930", "6m")  # 같은 종목을 다시 돌리면 '가장 최근' 실행만 합산돼요
    S.run_backtest(db, A, rid, "000660", "1y")
    runs = {r["code"]: r for r in S.list_runs(db, A, rid)}
    rep = S.rule_report(db, A, rid)
    last6 = next(r for r in S.list_runs(db, A, rid) if r["code"] == "005930")  # 목록은 최신순이라 첫 번째가 6m
    assert rep["backtest"]["companies"] == 2
    assert rep["backtest"]["trade_count"] == last6["trade_count"] + runs["000660"]["trade_count"]
    assert rep["actual"]["trade_count"] == 0 and rep["actual"]["avg_return"] is None
    acc = S.create_account(db, A, "실전", 10_000_000)
    d1, d2, _ = two_dates(db)
    S.create_trade(db, A, acc["account_id"], {"code": "005930", "side": "buy", "trade_date": d1, "qty": 10, "rule_id": rid})
    sell = S.create_trade(db, A, acc["account_id"], {"code": "005930", "side": "sell", "trade_date": d2, "qty": 10, "rule_id": rid})
    S.create_trade(db, A, acc["account_id"], {"code": "000660", "side": "buy", "trade_date": d1, "qty": 1})  # 규칙 없이 한 거래는 집계 제외
    rep = S.rule_report(db, A, rid)
    p1, p2 = close_on(db, "005930", d1), close_on(db, "005930", d2)
    cost = p1 * 10 * (1 + FEE_RATE)
    want = (p2 * 10 - sell["fee"] - cost) / cost * 100
    assert rep["actual"]["trade_count"] == 1 and rep["actual"]["avg_return"] == pytest.approx(want, abs=0.02)
    assert rep["actual"]["win_rate"] in (0.0, 100.0)
