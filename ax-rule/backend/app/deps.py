from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .dbapi import Db, sa_db


def client_id(x_client_id: str = Header(default="")) -> str:
    """로그인이 없어서 브라우저가 만든 임시 ID 로 내 규칙·계좌를 구분해요."""
    if not x_client_id or len(x_client_id) > 64:
        raise HTTPException(400, "X-Client-Id 헤더가 필요해요.")
    return x_client_id


def get_dbx(db: Session = Depends(get_db)) -> Db:
    return sa_db(db)
