"""인덱스가 있을 때/없을 때 실행 계획을 비교해요 (SQLite EXPLAIN QUERY PLAN + 평균 실행 시간).
실행: python scripts/explain.py     (PostgreSQL 에서는 같은 쿼리 앞에 EXPLAIN ANALYZE 를 붙이면 돼요)"""
import pathlib
import random
import re
import sqlite3
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app import sql  # noqa: E402

SCHEMA = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")


def build(with_index: bool):
    s = SCHEMA if with_index else re.sub(r"CREATE (UNIQUE )?INDEX [^;]*;", "", SCHEMA)  # UNIQUE 제약이 만드는 자동 인덱스는 남아요
    c = sqlite3.connect(":memory:")
    c.executescript(s)
    rnd = random.Random(1)
    c.execute("INSERT INTO sector(sector_id,name) VALUES (1,'테스트')")
    c.executemany("INSERT INTO company(company_id,code,name,market,sector_id) VALUES (?,?,?,?,1)", [(i, f"{i:06d}", f"회사{i}", "KOSPI") for i in range(1, 201)])
    c.executemany("INSERT INTO price_daily(company_id,trade_date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)",
                  [(i, f"2025-{1 + d // 28:02d}-{1 + d % 28:02d}", 100, 101, 99, 100, 1000) for i in range(1, 201) for d in range(300)])
    c.executemany("INSERT INTO rule(client_id,name,entry_type,entry_param,take_profit_pct,stop_loss_pct,max_hold_days,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                  [(f"c{i % 300}", f"규칙{i}", "ma_cross", 20, 8, 4, 20, "2026-01-01", "2026-01-01") for i in range(1, 1501)])
    c.executemany("INSERT INTO account(client_id,name,initial_cash,cash,created_at) VALUES (?,?,?,?,?)", [(f"c{i % 300}", f"계좌{i}", 10_000_000, 10_000_000, "2026-01-01") for i in range(1, 601)])
    c.executemany("INSERT INTO trade(account_id,company_id,rule_id,side,trade_date,price,qty,fee,memo) VALUES (?,?,?,?,?,?,?,?,'')",
                  [(1 + i % 600, 1 + i % 200, 1 + rnd.randrange(1500), "buy", f"2026-{1 + i % 9:02d}-{1 + i % 28:02d}", 100, 1, 0.1) for i in range(60000)])
    c.executemany("INSERT INTO backtest_run(rule_id,company_id,rule_text,start_date,end_date,trade_count,win_count,created_at) VALUES (?,?,'x','2025-01-01','2025-12-31',8,4,'2026-01-01')",
                  [(1 + i % 1500, 1 + i % 200) for i in range(6000)])
    c.executemany("INSERT INTO backtest_trade(run_id,entry_date,entry_price,exit_date,exit_price,exit_reason,return_pct,hold_days) VALUES (?,?,?,?,?,'tp',1.0,3)",
                  [(1 + i % 6000, "2025-02-01", 100, "2025-02-04", 101) for i in range(48000)])
    c.commit()
    return c


def q_marks(q):
    return re.sub(r":(\w+)", "?", q), re.findall(r":(\w+)", q)


CASES = [
    ("종목 시세 조회 (SERIES)", sql.SERIES, {"cid": 7, "since": "2025-06-01"}),
    ("계좌 거래 내역 (TRADES_VIEW)", sql.TRADES_VIEW, {"aid": 42}),
    ("규칙으로 한 거래 수 (규칙 삭제·리포트)", "SELECT COUNT(*) FROM trade WHERE rule_id = :r", {"r": 77}),
    ("백테스트 거래 목록 (RUN_TRADES)", sql.RUN_TRADES, {"id": 123}),
    ("규칙 성적 합산 (BACKTEST_AGG)", sql.BACKTEST_AGG, {"rid": 77}),
]

for with_index in (False, True):
    c = build(with_index)
    print(f"\n### {'인덱스 있음' if with_index else '인덱스 없음'}")
    for name, q, params in CASES:
        qq, keys = q_marks(q)
        args = [params[k] for k in keys]
        plan = " / ".join(r[3] for r in c.execute("EXPLAIN QUERY PLAN " + qq, args))
        t = time.perf_counter()
        for _ in range(30):
            c.execute(qq, args).fetchall()
        print(f"- {name}: `{plan}` — 평균 {(time.perf_counter() - t) / 30 * 1000:.2f} ms")
