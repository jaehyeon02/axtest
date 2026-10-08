import pathlib
import sqlite3
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.dbapi import lite_db  # noqa: E402
from app.seed_data import generate  # noqa: E402

SCHEMA = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
A, B = "client-a", "client-b"


def new_conn():
    """db/schema.sql 로 만든 빈 메모리 DB. FastAPI 없이도 서비스 로직 전체를 검증해요. (외래키 켬)"""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(SCHEMA)
    return c


def load_sample(conn):
    for table, rows in generate().items():
        for r in rows:
            conn.execute(f"INSERT INTO {table}({','.join(r)}) VALUES({','.join('?' * len(r))})",
                         [v.isoformat() if hasattr(v, "isoformat") else v for v in r.values()])
    conn.commit()


def rw(conn):
    """수집 코드(ingest.jobs)에 넣는 읽기/쓰기 함수 한 쌍."""

    def read(q, p):
        cur = conn.execute(q, p)
        return [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]

    def write(q, rows):
        rows = rows if isinstance(rows, list) else [rows]
        if rows:
            conn.executemany(q, rows)
        conn.commit()
        return len(rows)

    return read, write


@pytest.fixture()
def conn():
    c = new_conn()
    load_sample(c)
    return c


@pytest.fixture()
def db(conn):
    return lite_db(conn)


@pytest.fixture()
def empty():
    return new_conn()
