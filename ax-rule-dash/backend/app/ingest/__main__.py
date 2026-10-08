"""수집 명령.  python -m app.ingest <명령>

  init-db [--reset]   테이블 만들기(--reset: 전부 지우고 다시)
  sample              개발용 가상 샘플 데이터 넣기(인터넷 없이 화면 확인용)
  master              업종·종목 등록 + OpenDART 고유번호 채우기   (DART_API_KEY 있으면)
  prices [--years 2]  일봉 시세(pykrx). 이미 있으면 마지막 날 다음부터 이어받기
  fundamentals        일별 PER·PBR·EPS·BPS (pykrx)
  financials [--years 5] 연간 매출·영업이익·순이익 (OpenDART, DART_API_KEY 필요)
  all                 master → prices → fundamentals → financials
  status              테이블별 행 수와 최근 수집 기록
"""
import argparse
import sys

from .. import models  # noqa: F401
from ..database import Base, SessionLocal, engine, sql_writer
from ..seed import seed
from . import jobs, store
from .providers import DartError, LiveProvider


def _reader(db):
    from sqlalchemy import text

    def run(q, p):
        return [dict(r) for r in db.execute(text(q), p).mappings().all()]

    return run


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m app.ingest", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["init-db", "sample", "master", "prices", "fundamentals", "financials", "all", "status"])
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--years", type=int)
    a = ap.parse_args(argv)

    if a.cmd == "init-db":
        if a.reset:
            Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        print("테이블 준비 완료")
        return 0

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        read, write = _reader(db), sql_writer(db)
        if a.cmd == "sample":
            seed(db)
            print("샘플 데이터 적재 완료(이미 데이터가 있으면 아무것도 하지 않아요)")
            return 0
        if a.cmd == "status":
            for name, q in store.COUNT_TABLE.items():
                print(f"{name:12s} {read(q, {})[0]['n']:>8,}")
            for r in read("SELECT job, source, status, row_count, message, finished_at FROM ingestion_log ORDER BY log_id DESC LIMIT 8", {}):
                print(f"  {r['finished_at']}  {r['job']:8s} {r['source']:8s} {r['status']:4s} {r['row_count']:>7}  {r['message']}")
            return 0
        if read(store.HAS_SAMPLE, {})[0]["n"]:
            print("⚠️ 이 DB에는 가상 샘플 데이터가 들어 있어요. 실데이터와 섞이지 않게 `python -m app.ingest init-db --reset` 로 비우고 다시 실행하세요.")
            return 2
        provider = LiveProvider()
        try:
            if a.cmd in ("master", "all"):
                print(f"master: 종목 {jobs.load_master(write, provider if provider.key else None)}개 등록")
            for job, fn in (("prices", jobs.load_prices), ("fundamentals", jobs.load_fundamentals), ("financials", jobs.load_financials)):
                if a.cmd in (job, "all"):
                    if job == "financials" and not provider.key:
                        print("financials: DART_API_KEY 가 없어서 건너뛰어요 (https://opendart.fss.or.kr 에서 무료 발급)")
                        continue
                    kwargs = {"years": a.years} if a.years else {}
                    n, failed = fn(read, write, provider, **kwargs)
                    print(f"{job}: {n:,}행" + (f"  (실패 {len(failed)}건: {failed[0]})" if failed else ""))
        except DartError as e:
            print(f"❌ {e}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
