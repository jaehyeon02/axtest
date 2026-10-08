"""DB 어댑터: SQL 문장 + 이름 있는 파라미터(:name)를 실행하는 얇은 계층.

운영에서는 SQLAlchemy 세션(SaDb), 테스트·개발 확인에서는 sqlite3 연결(LiteDb)을 넣어요.
둘 다 **같은 SQL 문장**을 그대로 실행하고, 결과는 날짜→'YYYY-MM-DD' 문자열, 숫자→float 로 맞춰서 돌려줘요.
service.py 의 모든 로직이 이 계층 위에서 돌아가므로, sqlite3 로 검증한 로직이 그대로 운영 경로에서 쓰여요.
"""
from datetime import date, datetime
from decimal import Decimal


def _norm(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.isoformat(sep=" ", timespec="seconds")
    if isinstance(v, date):
        return v.isoformat()
    return v


class Db:
    def __init__(self, execute, commit, rollback):
        self._execute, self.commit, self.rollback = execute, commit, rollback

    def all(self, q: str, **p) -> list:
        rows, _ = self._execute(q, p)
        return [{k: _norm(v) for k, v in r.items()} for r in rows]

    def one(self, q: str, **p):
        rows = self.all(q, **p)
        return rows[0] if rows else None

    def run(self, q: str, **p) -> int:
        """INSERT/UPDATE/DELETE. 바뀐 행 수를 돌려줘요. (커밋은 service 가 직접 해요.)"""
        return self._execute(q, p)[1]

    def insert(self, q: str, **p) -> int:
        """`INSERT ... RETURNING xxx_id` 문장을 실행해서 새 id 를 돌려줘요. (SQLite 3.35+ 와 PostgreSQL 이 지원)"""
        rows, _ = self._execute(q, p)
        return list(rows[0].values())[0]


def lite_db(conn) -> Db:
    """sqlite3 연결용. conn.row_factory 는 이 함수가 설정해요."""
    import sqlite3

    conn.row_factory = sqlite3.Row

    def execute(q, p):
        cur = conn.execute(q, p)
        rows = [dict(r) for r in cur.fetchall()] if cur.description else []
        return rows, cur.rowcount

    return Db(execute, conn.commit, conn.rollback)


def sa_db(session) -> Db:
    """SQLAlchemy 세션용."""
    from sqlalchemy import text

    def execute(q, p):
        res = session.execute(text(q), p)
        rows = [dict(r) for r in res.mappings().all()] if res.returns_rows else []
        return rows, res.rowcount

    return Db(execute, session.commit, session.rollback)
