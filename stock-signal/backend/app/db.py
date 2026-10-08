from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """요청마다 세션을 하나 열고, 끝나면 닫는다 (FastAPI Dependency Injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
