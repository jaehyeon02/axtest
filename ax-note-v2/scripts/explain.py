"""인덱스가 있을 때/없을 때 쿼리 실행 계획을 비교해요 (SQLite EXPLAIN QUERY PLAN).
실행: python scripts/explain.py   → 결과를 표준출력으로 내보내요 (docs/EXPLAIN.md 에 붙여 둠)
PostgreSQL 에서는 같은 쿼리 앞에 `EXPLAIN ANALYZE` 를 붙이면 돼요."""
import pathlib
import re
import sqlite3
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app import sql  # noqa: E402

SCHEMA = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")


def build(with_index: bool):
    s = SCHEMA if with_index else re.sub(r"CREATE (UNIQUE )?INDEX [^;]*;", "", SCHEMA)
    c = sqlite3.connect(":memory:")
    c.executescript(s)
    c.execute("INSERT INTO sector(sector_id,name) VALUES (1,'테스트')")
    n_co, n_day = 200, 250  # 회사 200개 × 250거래일 = 시세 5만 행
    c.executemany("INSERT INTO company(company_id,code,name,market,sector_id) VALUES (?,?,?,?,1)",
                  [(i, f"{i:06d}", f"회사{i}", "KOSPI") for i in range(1, n_co + 1)])
    rows = [(i, f"2026-{1 + d // 28:02d}-{1 + d % 28:02d}", 100, 101, 99, 100, 1000) for i in range(1, n_co + 1) for d in range(n_day)]
    c.executemany("INSERT INTO price_daily(company_id,trade_date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)", rows)
    c.executemany("INSERT INTO document(company_id,doc_type,title,source,published_date,rcept_no) VALUES (?,?,?,?,?,?)",
                  [(1 + i % n_co, "filing", f"공시{i}", "DART", f"2026-{1 + i % 9:02d}-{1 + i % 28:02d}", f"R{i:08d}") for i in range(20000)])
    c.commit()
    return c


def to_qmark(q):
    return re.sub(r":(\w+)", "?", q), re.findall(r":(\w+)", q)


CASES = [
    ("종목 1년 시세 (SERIES)", sql.SERIES, {"cid": 7, "since": "2026-01-01"}),
    ("종목 공시 목록 (DOCUMENTS)", sql.DOCUMENTS, {"cid": 7, "since": "2026-01-01", "client": "x"}),
    ("접수번호로 공시 찾기(중복 방지)", "SELECT doc_id FROM document WHERE rcept_no = :r", {"r": "R00012345"}),
]

for with_index in (False, True):
    c = build(with_index)
    print(f"\n### {'인덱스 있음' if with_index else '인덱스 없음'}")
    for name, q, params in CASES:
        qq, keys = to_qmark(q)
        args = [params[k] for k in keys]
        plan = " / ".join(r[3] for r in c.execute("EXPLAIN QUERY PLAN " + qq, args))
        t = time.perf_counter()
        for _ in range(50):
            c.execute(qq, args).fetchall()
        ms = (time.perf_counter() - t) / 50 * 1000
        print(f"- {name}: `{plan}` — 평균 {ms:.2f} ms")
