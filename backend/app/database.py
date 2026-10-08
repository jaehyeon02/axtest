"""DB 연결 설정. DATABASE_URL 환경변수가 없으면 SQLite 파일을 사용합니다."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./stock.db")

# SQLite는 스레드 제약 옵션이 필요합니다. PostgreSQL 등은 필요 없어요.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """요청마다 DB 세션을 열고, 끝나면 닫는 FastAPI 의존성."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
