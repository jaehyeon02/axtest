"""수집 작업 흐름. `read(sql, params) -> list[dict]`, `write(sql, rows) -> 행 수`, `provider` 를 받아서
운영에서는 SQLAlchemy + LiveProvider, 테스트에서는 sqlite3 + 가짜 provider 를 넣어요."""
from datetime import date, timedelta

from . import store
from .universe import UNIVERSE


def load_master(write):
    """업종·종목 등록 (universe.py 의 목록)."""
    write(store.UPSERT_SECTOR, [{"name": s} for s in dict.fromkeys(u[3] for u in UNIVERSE)])
    n = write(store.UPSERT_COMPANY, [{"code": c, "name": nm, "market": m, "sector": s} for c, nm, m, s in UNIVERSE])
    store.log(write, "master", "manual", "ok", n)
    return n


def load_prices(read, write, provider, years: int = 2, today: date | None = None):
    today = today or date.today()
    total, failed = 0, []
    for c in read(store.SELECT_COMPANIES, {}):
        try:
            last = read(store.LAST_PRICE, {"cid": c["company_id"]})[0]["d"]
            start = date.fromisoformat(str(last)[:10]) + timedelta(days=1) if last else today - timedelta(days=365 * years)  # 이어받기(증분)
            if start > today:
                continue
            rows, _skipped = provider.prices(c["code"], start, today)
            total += write(store.UPSERT_PRICE, [{"cid": c["company_id"], **r} for r in rows])
        except Exception as e:  # 한 종목 실패가 전체를 멈추지 않게 하고, 실패는 기록으로 남겨요.
            failed.append(f"{c['code']}: {type(e).__name__}: {e}"[:120])
    store.log(write, "prices", "pykrx", "fail" if failed and not total else "ok", total, "; ".join(failed[:3]))
    return total, failed
