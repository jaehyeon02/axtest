"""수집 로직 테스트: 네트워크 대신 가짜 provider 를 넣어서 '여러 번 실행해도 안전한지', '한 종목이 실패해도 계속되는지'를 확인해요."""
import json
from datetime import date

from conftest import rw
from app.ingest import jobs, parsers, store
from app.ingest.universe import UNIVERSE


class Fake:
    """provider 와 같은 모양의 가짜. 호출 기록을 남겨서 '이어받기'가 맞는지 볼 수 있어요."""

    def __init__(self, fail_code=None, fixed=False):
        self.fail_code, self.fixed, self.price_calls = fail_code, fixed, []

    def corp_codes(self):
        return {code: f"{i:08d}" for i, (code, *_rest) in enumerate(UNIVERSE, start=1)}

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

    def filings(self, corp_code, start, end):
        return [{"title": "분기보고서 (2026.06)", "body": "제출인: 회사", "d": "2026-08-14", "rcept": f"2026{corp_code}01", "url": "https://dart.fss.or.kr/x"}]

    def financial(self, corp_code, year):
        return {"revenue": 1000.0 + year, "operating_profit": 100.0, "net_income": 80.0}


def counts(c):
    return {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("sector", "company", "price_daily", "document", "financial_year", "ingestion_log")}


def run_all(c, p, today=date(2026, 10, 7)):
    read, write = rw(c)
    jobs.load_master(write, p)
    jobs.load_prices(read, write, p, years=1, today=today)
    jobs.load_filings(read, write, p, today=today)
    jobs.load_financials(read, write, p, years=3, today=today)


def test_ingest_loads_expected_rows(empty):
    run_all(empty, Fake())
    n = counts(empty)
    assert n["company"] == len(UNIVERSE) and n["sector"] == 5
    assert n["price_daily"] == 3 * len(UNIVERSE) and n["document"] == len(UNIVERSE) and n["financial_year"] == 3 * len(UNIVERSE)
    assert empty.execute("SELECT COUNT(*) FROM company WHERE corp_code IS NULL").fetchone()[0] == 0


def test_ingest_is_idempotent(empty):
    p = Fake(fixed=True)
    run_all(empty, p)
    first = {k: v for k, v in counts(empty).items() if k != "ingestion_log"}
    run_all(empty, p)  # 같은 데이터를 다시 받아도 행이 늘면 안 돼요
    assert {k: v for k, v in counts(empty).items() if k != "ingestion_log"} == first
    assert counts(empty)["ingestion_log"] == 2 * 4  # 실행할 때마다 작업(master·prices·filings·financials)별 기록이 남아요


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
    p = Fake(fail_code="000660")
    jobs.load_master(write, p)
    total, failed = jobs.load_prices(read, write, p, years=1, today=date(2026, 10, 7))
    assert total == 3 * (len(UNIVERSE) - 1) and len(failed) == 1 and "000660" in failed[0]
    log = empty.execute("SELECT status, message FROM ingestion_log WHERE job = 'prices'").fetchone()
    assert log["status"] == "ok" and "000660" in log["message"]  # 실패도 기록에 남아요


def test_filings_need_master_first(empty):
    read, write = rw(empty)
    jobs.load_master(write, None)  # 키가 없어서 corp_code 가 비어 있는 경우
    total, failed = jobs.load_filings(read, write, Fake(), today=date(2026, 10, 7))
    assert total == 0 and len(failed) == len(UNIVERSE) and "corp_code" in failed[0]
    assert empty.execute("SELECT status FROM ingestion_log WHERE job = 'filings'").fetchone()[0] == "fail"


# ───────── 파서(외부 응답 → 테이블 모양) ─────────
def test_parse_ohlcv_skips_bad_rows():
    recs = [
        {"날짜": "2026-10-01", "시가": 100, "고가": 110, "저가": 90, "종가": 105, "거래량": 500},
        {"날짜": "2026-10-02", "시가": 0, "고가": 0, "저가": 0, "종가": 0, "거래량": 0},        # 거래정지
        {"날짜": "2026-10-05", "시가": 100, "고가": 99, "저가": 90, "종가": 105, "거래량": 500},  # 고가가 종가보다 낮음
        {"날짜": "2026-10-06", "시가": "x", "고가": 1, "저가": 1, "종가": 1, "거래량": 1},       # 숫자가 아님
    ]
    rows, skipped = parsers.parse_ohlcv(recs)
    assert [r["d"] for r in rows] == ["2026-10-01"] and skipped == 3


def test_parse_filings_filters_noise_and_builds_link():
    payload = {"status": "000", "list": [
        {"report_nm": "분기보고서 (2026.06)", "rcept_no": "20260814000123", "flr_nm": "삼성전자", "rcept_dt": "20260814", "rm": ""},
        {"report_nm": "임원ㆍ주요주주특정증권등소유상황보고서", "rcept_no": "20260815000001", "flr_nm": "홍길동", "rcept_dt": "20260815"},
        {"report_nm": "단일판매ㆍ공급계약체결", "rcept_no": "20260816000002", "flr_nm": "삼성전자", "rcept_dt": "20260816", "rm": "유"},
    ]}
    rows = parsers.parse_filings(payload)
    assert [r["rcept"] for r in rows] == ["20260814000123", "20260816000002"]
    assert rows[0]["d"] == "2026-08-14" and rows[0]["url"].endswith("rcpNo=20260814000123") and "비고: 유" in rows[1]["body"]
    assert parsers.parse_filings({"status": "013"}) == []  # 조회 결과 없음


def test_parse_corp_codes():
    xml = "<result><list><corp_code>00126380</corp_code><corp_name>삼성전자</corp_name><stock_code>005930</stock_code></list>" \
          "<list><corp_code>00999999</corp_code><corp_name>비상장</corp_name><stock_code> </stock_code></list></result>".encode()
    assert parsers.parse_corp_codes(xml) == {"005930": "00126380"}


def test_parse_financial_converts_to_eok_and_handles_missing():
    payload = {"list": [
        {"sj_div": "BS", "account_id": "ifrs-full_Assets", "account_nm": "자산총계", "thstrm_amount": "999"},
        {"sj_div": "CIS", "account_id": "ifrs-full_Revenue", "account_nm": "매출액", "thstrm_amount": "300,870,903,000,000"},
        {"sj_div": "CIS", "account_id": "dart_OperatingIncomeLoss", "account_nm": "영업이익", "thstrm_amount": "32,725,961,000,000"},
        {"sj_div": "CIS", "account_id": "ifrs-full_ProfitLoss", "account_nm": "당기순이익", "thstrm_amount": "-1,000,000,000"},
    ]}
    assert parsers.parse_financial(payload) == {"revenue": 3008709.0, "operating_profit": 327259.6, "net_income": -10.0}
    assert parsers.parse_financial({"list": [{"sj_div": "CIS", "account_nm": "매출액", "thstrm_amount": "100,000,000"}]}) is None  # 영업이익이 없으면 버려요
