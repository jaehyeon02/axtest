"""관심종목 CRUD. 같은 종목은 한 번만 담을 수 있고(UNIQUE), 내 것만 보여요."""
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_id, get_repo
from ..models import Company, Watchlist
from ..repo import Repo
from ..schemas import WatchOut

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


def _list(repo: Repo, db: Session, cid: str) -> List[dict]:
    quotes = {c["code"]: c for c in repo.companies("")}
    rows = db.execute(
        select(Watchlist, Company).join(Company, Company.company_id == Watchlist.company_id)
        .where(Watchlist.client_id == cid).order_by(Watchlist.created_at.desc(), Watchlist.watch_id.desc())
    ).all()
    return [{"watch_id": w.watch_id, "company": quotes[c.code], "created_at": w.created_at} for w, c in rows]


@router.get("", response_model=List[WatchOut])
def list_watch(cid: str = Depends(client_id), repo: Repo = Depends(get_repo), db: Session = Depends(get_db)):
    return _list(repo, db, cid)


@router.put("/{code}", response_model=List[WatchOut])
def add_watch(code: str, cid: str = Depends(client_id), repo: Repo = Depends(get_repo), db: Session = Depends(get_db)):
    """관심종목에 담기. 이미 담겨 있어도 오류 없이 같은 결과를 돌려줘요(여러 번 눌러도 안전)."""
    company = db.scalar(select(Company).where(Company.code == code))
    if not company:
        raise HTTPException(404, "종목을 찾을 수 없어요.")
    db.add(Watchlist(client_id=cid, company_id=company.company_id, created_at=datetime.now()))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return _list(repo, db, cid)


@router.delete("/{code}", response_model=List[WatchOut])
def remove_watch(code: str, cid: str = Depends(client_id), repo: Repo = Depends(get_repo), db: Session = Depends(get_db)):
    w = db.scalar(select(Watchlist).join(Company, Company.company_id == Watchlist.company_id).where(Watchlist.client_id == cid, Company.code == code))
    if not w:
        raise HTTPException(404, "관심종목에 없는 종목이에요.")
    db.delete(w)
    db.commit()
    return _list(repo, db, cid)
