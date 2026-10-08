"""조회용 SQL 실행 계층.

`execute(sql, params) -> list[dict]` 함수 하나만 받아요. 운영에서는 SQLAlchemy 세션, 테스트에서는 sqlite3 를 넣고
둘 다 같은 SQL 문장(sql.py)을 실행합니다. 결과는 날짜는 date, 숫자는 float 로 맞춰서 돌려줘요.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from . import sql


def to_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def _clean(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if k.endswith("_date") or k == "d":
            out[k] = to_date(v) if v is not None else None
        elif isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


class Repo:
    def __init__(self, execute, client: str = ""):
        self._run = execute
        self.client = client

    def _q(self, query, **params):
        return [_clean(r) for r in self._run(query, params)]

    def companies(self, q: str = ""):
        rows = self._q(sql.COMPANIES, like=f"%{q.strip()}%")
        latest = {r["company_id"]: r for r in self._q(sql.LATEST_ALL)}
        for r in rows:
            last = latest.get(r["company_id"])
            r["price"] = last["close"] if last else None
            r["change_rate"] = round((last["close"] / last["prev_close"] - 1) * 100, 2) if last and last["prev_close"] else 0.0
            r["trade_date"] = last["trade_date"] if last else None
        return rows

    def company(self, code: str):
        rows = self._q(sql.COMPANY_BY_CODE, code=code)
        return rows[0] if rows else None

    def latest_date(self, cid: int):
        rows = self._q(sql.LATEST_DATE, cid=cid)
        return rows[0]["d"] if rows else None

    def series(self, cid: int, since: date):
        return self._q(sql.SERIES, cid=cid, since=since.isoformat())

    def movers(self, cid: int, since: date, threshold: float = 4.0):
        return self._q(sql.MOVERS, cid=cid, since=since.isoformat(), th=threshold)

    def monthly(self, cid: int):
        return self._q(sql.MONTHLY, cid=cid)

    def financials(self, cid: int, n: int = 8):
        return self._q(sql.FINANCIALS, cid=cid, n=n)

    def peers(self, cid: int):
        return self._q(sql.PEERS, cid=cid)

    def analysis(self, cid: int):
        """가격 흐름 숫자: 기간 수익률·최대 낙폭·변동성·120일선 괴리율. 윈도 함수 계산은 SQL, 표준편차만 파이썬."""
        last = self._q(sql.ANALYSIS_LAST, cid=cid)
        if not last:
            return None
        last = last[0]
        today = last["trade_date"]
        out = {"trade_date": today, "close": last["close"], "returns": {}}
        for label, key in (("1개월", "c21"), ("3개월", "c63"), ("6개월", "c126")):
            out["returns"][label] = round((last["close"] / last[key] - 1) * 100, 2) if last[key] else None
        out["ma120"] = round(last["ma120"], 0) if last["n120"] == 120 else None
        out["ma120_gap"] = round((last["close"] / last["ma120"] - 1) * 100, 2) if last["n120"] == 120 else None
        year_ago = today.replace(year=today.year - 1) if not (today.month == 2 and today.day == 29) else today.replace(year=today.year - 1, day=28)
        mdd = self._q(sql.ANALYSIS_MDD, cid=cid, since=year_ago.isoformat())
        out["mdd"] = round(mdd[0]["mdd"], 2) if mdd and mdd[0]["mdd"] is not None else None
        rets = [r["ret_pct"] for r in self._q(sql.DAILY_RETURNS, cid=cid, since=(today - timedelta(days=90)).isoformat())]
        if len(rets) >= 20:
            m = sum(rets) / len(rets)
            sd = (sum((x - m) ** 2 for x in rets) / (len(rets) - 1)) ** 0.5
            out["volatility_daily"] = round(sd, 2)
            out["volatility_annual"] = round(sd * (252 ** 0.5), 1)
        else:
            out["volatility_daily"] = out["volatility_annual"] = None
        return out

    def documents(self, cid: int, since: date):
        return self._q(sql.DOCUMENTS, cid=cid, since=since.isoformat(), client=self.client)

    def document(self, doc_id: int):
        rows = self._q(sql.DOCUMENT_BY_ID, doc_id=doc_id)
        return rows[0] if rows else None

    def price(self, price_id: int):
        rows = self._q(sql.PRICE_BY_ID, price_id=price_id)
        return rows[0] if rows else None
