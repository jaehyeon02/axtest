import pathlib
import sqlite3
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.repo import Repo  # noqa: E402
from app.seed_data import generate  # noqa: E402

SCHEMA = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")


def new_db():
    """db/schema.sql 로 만든 빈 메모리 DB. FastAPI 없이도 SQL·분석·수집 로직을 검증해요."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(SCHEMA)
    return c


def rw(conn):
    """수집 코드(ingest.jobs)에 넣는 읽기/쓰기 함수 한 쌍. 운영에서는 같은 모양의 SQLAlchemy 버전이 들어가요."""

    def read(q, p):
        return [dict(r) for r in conn.execute(q, p).fetchall()]

    def write(q, rows):
        rows = rows if isinstance(rows, list) else [rows]
        if rows:
            conn.executemany(q, rows)
        conn.commit()
        return len(rows)

    return read, write


def load_sample(c):
    for table, rows in generate().items():
        for r in rows:
            vals = [v.isoformat() if hasattr(v, "isoformat") else v for v in r.values()]
            c.execute(f"INSERT INTO {table}({','.join(r)}) VALUES({','.join('?' * len(r))})", vals)
    c.commit()
    return c


@pytest.fixture(scope="session")
def conn():
    return load_sample(new_db())


@pytest.fixture(scope="session")
def repo(conn):
    return Repo(lambda q, p: [dict(r) for r in conn.execute(q, p).fetchall()])


@pytest.fixture()
def empty():
    return new_db()
