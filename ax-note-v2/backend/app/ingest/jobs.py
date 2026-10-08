"""수집 작업 흐름. `read(sql, params) -> list[dict]`, `write(sql, rows) -> 행 수`, `provider` 를 받아서
운영에서는 SQLAlchemy + LiveProvider, 테스트에서는 sqlite3 + 가짜 provider 를 넣어요."""
from datetime import date, timedelta

from . import store
from .universe import UNIVERSE


def load_master(write, provider=None):
    """업종·종목을 넣고, (키가 있으면) OpenDART 고유번호도 채워요."""
    corp = provider.corp_codes() if provider else {}
    write(store.UPSERT_SECTOR, [{"name": s} for s in dict.fromkeys(u[3] for u in UNIVERSE)])
    n = write(store.UPSERT_COMPANY, [{"code": c, "name": nm, "market": m, "sector": s, "corp_code": corp.get(c)} for c, nm, m, s in UNIVERSE])
    store.log(write, "master", "opendart" if corp else "manual", "ok", n, "" if corp else "고유번호 없이 종목만 등록")
    return n


def _each_company(read, write, job, source, fn):
    total, failed = 0, []
    for c in read(store.SELECT_COMPANIES, {}):
        try:
            total += fn(c)
        except Exception as e:  # 한 종목 실패가 전체를 멈추지 않게 하고, 실패는 기록으로 남겨요.
            failed.append(f"{c['code']}: {type(e).__name__}: {e}"[:120])
    store.log(write, job, source, "fail" if failed and not total else "ok", total, "; ".join(failed[:3]))
    return total, failed


def load_prices(read, write, provider, years: int = 2, today: date | None = None):
    today = today or date.today()

    def one(c):
        last = read(store.LAST_PRICE, {"cid": c["company_id"]})[0]["d"]
        start = date.fromisoformat(str(last)[:10]) + timedelta(days=1) if last else today - timedelta(days=365 * years)  # 이어받기(증분)
        if start > today:
            return 0
        rows, _skipped = provider.prices(c["code"], start, today)
        return write(store.UPSERT_PRICE, [{"cid": c["company_id"], **r} for r in rows])

    return _each_company(read, write, "prices", "pykrx", one)


def load_filings(read, write, provider, days: int = 365, today: date | None = None):
    today = today or date.today()

    def one(c):
        if not c["corp_code"]:
            raise ValueError("corp_code 없음(master 를 먼저 실행하세요)")
        rows = provider.filings(c["corp_code"], today - timedelta(days=days), today)
        return write(store.INSERT_FILING, [{"cid": c["company_id"], **r} for r in rows])

    return _each_company(read, write, "filings", "opendart", one)


def load_financials(read, write, provider, years: int = 5, today: date | None = None):
    this_year = (today or date.today()).year

    def one(c):
        if not c["corp_code"]:
            raise ValueError("corp_code 없음(master 를 먼저 실행하세요)")
        rows = []
        for fy in range(this_year - years, this_year):  # 사업보고서는 다음 해 3월에 나와서 '작년'까지만 있어요
            got = provider.financial(c["corp_code"], fy)
            if got:
                rows.append({"cid": c["company_id"], "fy": fy, **got})
        return write(store.UPSERT_FINANCIAL, rows)

    return _each_company(read, write, "financials", "opendart", one)
