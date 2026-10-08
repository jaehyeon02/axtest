import os

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# 기본은 SQLite 파일. PostgreSQL 은 DATABASE_URL=postgresql+psycopg://user:pw@localhost/axnote 로 바꾸면 돼요.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ax_note.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys = ON")  # SQLite 는 기본으로 외래키·CASCADE 를 꺼 두기 때문


SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def sql_executor(db):
    """repo.Repo 에 넣는 실행 함수: SQL 문장 + 파라미터 → 딕셔너리 목록"""

    def run(query, params):
        return [dict(r) for r in db.execute(text(query), params).mappings().all()]

    return run


def sql_writer(db):
    """수집 스크립트용 쓰기 함수: SQL 문장 + 파라미터 목록 → 실행 후 커밋(행 수를 돌려줘요)."""

    def run(query, rows):
        rows = rows if isinstance(rows, list) else [rows]
        if rows:
            db.execute(text(query), rows)
        db.commit()
        return len(rows)

    return run
