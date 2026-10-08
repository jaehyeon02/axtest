from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .database import get_db, sql_executor
from .repo import Repo


def client_id(x_client_id: str = Header(default="")) -> str:
    """로그인이 없어서 브라우저가 만든 임시 ID 로 내 노트/기록을 구분해요."""
    if not x_client_id or len(x_client_id) > 64:
        raise HTTPException(400, "X-Client-Id 헤더가 필요해요.")
    return x_client_id


def get_repo(db: Session = Depends(get_db), x_client_id: str = Header(default="")) -> Repo:
    return Repo(sql_executor(db), client=x_client_id[:64])


def company_or_404(repo: Repo, code: str) -> dict:
    c = repo.company(code)
    if not c:
        raise HTTPException(404, "종목을 찾을 수 없어요.")
    return c
