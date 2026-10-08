"""수집 로직 테스트: 네트워크 대신 가짜 provider 를 넣어서 '여러 번 실행해도 안전한지', '한 종목이 실패해도 계속되는지'를 확인해요."""
from datetime import date

from conftest import rw
from app.ingest import jobs, parsers
from app.ingest.universe import UNIVERSE


class Fake:
    """provider 와 같은 모양의 가짜. 호출 기록을 남겨서 '이어받기'가 맞는지 볼 수 있어요."""

    def __init__(self, fail_code=None, fixed=False):
        self.fail_code, self.fixed, self.price_calls = fail_code, fixed, []

    def prices(self, code, start, end):
        self.price_calls.append((code, start))
        if code == self.fail_code:
            raise ConnectionError("timeout")
        rows, d = [], (date(2026, 9, 1) if self.fixed else start)  # fixed: 언제 물어도 같은 응답(이미 있는 날짜를 다시 받는 상황)
        while d <= end and len(rows) < 3:
            if d.weekday() < 5:
                rows.append({"d": d.isoformat(), "o": 100.0, "h": 110.0, "l": 95.0, "c": 105.0, "v": 1000})
            d = date.fromordinal(d.toordinal() + 1)
        return rows, 0


def counts(c):
    return {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("sector", "company", "price_daily", "ingestion_log")}


def run_all(c, p, today=date(2026, 10, 7)):
    read, write = rw(c)
    jobs.load_master(write)
    jobs.load_prices(read, write, p, years=1, today=today)


def test_ingest_loads_expected_rows(empty):
    run_all(empty, Fake())
    n = counts(empty)
    assert n["company"] == len(UNIVERSE) and n["sector"] == 5 and n["price_daily"] == 3 * len(UNIVERSE)


def test_ingest_is_idempotent(empty):
    p = Fake(fixed=True)
    run_all(empty, p)
    first = {k: v for k, v in counts(empty).items() if k != "ingestion_log"}
    run_all(empty, p)  # 같은 데이터를 다시 받아도 행이 늘면 안 돼요
    assert {k: v for k, v in counts(empty).items() if k != "ingestion_log"} == first
    assert counts(empty)["ingestion_log"] == 2 * 2  # 실행할 때마다 작업(master·prices)별 기록이 남아요


def test_prices_resume_from_last_date(empty):
    p = Fake()
    run_all(empty, p)
    last = empty.execute("SELECT MAX(trade_date) FROM price_daily WHERE company_id = 1").fetchone()[0]
    p.price_calls.clear()
    read, write = rw(empty)
    jobs.load_prices(read, write, p, years=1, today=date(2026, 10, 7))
    assert p.price_calls[0][1] == date.fromisoformat(last) + (date(2026, 1, 2) - date(2026, 1, 1))  # 마지막 날 다음 날부터


def test_one_company_failure_does_not_stop_others(empty):
    read, write = rw(empty)
    jobs.load_master(write)
    total, failed = jobs.load_prices(read, write, Fake(fail_code="000660"), years=1, today=date(2026, 10, 7))
    assert total == 3 * (len(UNIVERSE) - 1) and len(failed) == 1 and "000660" in failed[0]
    log = empty.execute("SELECT status, message FROM ingestion_log WHERE job = 'prices'").fetchone()
    assert log["status"] == "ok" and "000660" in log["message"]  # 실패도 기록에 남아요


def test_parse_ohlcv_skips_bad_rows():
    recs = [
        {"날짜": "2026-10-01", "시가": 100, "고가": 110, "저가": 90, "종가": 105, "거래량": 500},
        {"날짜": "2026-10-02", "시가": 0, "고가": 0, "저가": 0, "종가": 0, "거래량": 0},        # 거래정지
        {"날짜": "2026-10-05", "시가": 100, "고가": 99, "저가": 90, "종가": 105, "거래량": 500},  # 고가가 종가보다 낮음
        {"날짜": "2026-10-06", "시가": "x", "고가": 1, "저가": 1, "종가": 1, "거래량": 1},       # 숫자가 아님
    ]
    rows, skipped = parsers.parse_ohlcv(recs)
    assert [r["d"] for r in rows] == ["2026-10-01"] and skipped == 3
