"""수집 명령.  python -m app.ingest <명령>

  init-db [--reset]   테이블 만들기(--reset: 전부 지우고 다시)
  sample              개발용 가상 샘플 데이터 넣기(인터넷·API 키 없이 화면 확인용)
  master              업종·종목 등록 + OpenDART 고유번호 채우기        (DART_API_KEY 필요)
  prices [--years 2]  일봉 시세(pykrx). 이미 있으면 마지막 날 다음부터 이어받기
  filings [--days 365] 공시(OpenDART)
  financials [--years 5] 연간 재무(OpenDART)
  all                 master → prices → filings → financials
  status              테이블별 행 수와 최근 수집 기록
"""
import argparse
import sys

from ..database import Base, SessionLocal, engine, sql_executor, sql_writer
from .. import models  # noqa: F401
from ..seed import seed
from . import jobs, store
from .providers import DartError, LiveProvider


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m app.ingest", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["init-db", "sample", "master", "prices", "filings", "financials", "all", "status"])
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--years", type=int)
    ap.add_argument("--days", type=int, default=365)
    a = ap.parse_args(argv)

    if a.cmd == "init-db":
        if a.reset:
            Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        print("테이블 준비 완료")
        return 0

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        read, write = sql_executor(db), sql_writer(db)
        if a.cmd == "sample":
            seed(db)
            print("샘플 데이터 적재 완료(이미 데이터가 있으면 아무것도 하지 않아요)")
            return 0
        if a.cmd == "status":
            for name, q in store.COUNT_TABLE.items():
                print(f"{name:16s} {read(q, {})[0]['n']:>8,}")
            for r in read("SELECT job, source, status, row_count, message, finished_at FROM ingestion_log ORDER BY log_id DESC LIMIT 8", {}):
                print(f"  {r['finished_at']}  {r['job']:10s} {r['source']:8s} {r['status']:4s} {r['row_count']:>7}  {r['message']}")
            return 0
        if read(store.HAS_SAMPLE, {})[0]["n"]:
            print("⚠️ 이 DB에는 가상 샘플 데이터가 들어 있어요. 실데이터와 섞이지 않게 `python -m app.ingest init-db --reset` 로 비우고 다시 실행하세요.")
            return 2
        provider = LiveProvider()
        try:
            return _run(a, read, write, provider)
        except DartError as e:
            print(f"❌ {e}")
            return 1
    return 0


def _run(a, read, write, provider):
    todo = ["master", "prices", "filings", "financials"] if a.cmd == "all" else [a.cmd]
    for job in todo:
        if job == "master":
            n = jobs.load_master(write, provider)
            print(f"master: 종목 {n}개 등록")
            continue
        fn = {"prices": jobs.load_prices, "filings": jobs.load_filings, "financials": jobs.load_financials}[job]
        kwargs = {"days": a.days} if job == "filings" else ({"years": a.years} if a.years else {})
        n, failed = fn(read, write, provider, **kwargs)
        print(f"{job}: {n:,}행" + (f"  (실패 {len(failed)}건: {failed[0]})" if failed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
