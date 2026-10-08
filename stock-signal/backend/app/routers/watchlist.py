from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import queries
from app.db import get_db
from app.models import Company, Member, Watch
from app.schemas import WatchCreate, WatchOut

router = APIRouter(prefix="/watchlist", tags=["관심종목"])


@router.get("", summary="내 관심종목 + 최신 신호등 (member_id 필수)")
def list_watchlist(member_id: int, db: Session = Depends(get_db)):
    if db.get(Member, member_id) is None:
        raise HTTPException(404, "존재하지 않는 회원입니다.")
    return [dict(r) for r in db.execute(text(queries.WATCHLIST), {"member_id": member_id}).mappings().all()]


@router.post("", response_model=WatchOut, status_code=201, summary="관심종목 추가")
def add_watch(body: WatchCreate, db: Session = Depends(get_db)):
    if db.get(Member, body.member_id) is None:
        raise HTTPException(404, "존재하지 않는 회원입니다.")
    if db.get(Company, body.company_id) is None:
        raise HTTPException(404, "존재하지 않는 종목입니다.")
    watch = Watch(**body.model_dump())
    db.add(watch)
    db.commit()  # 같은 회원·종목 중복 → 409
    db.refresh(watch)
    return watch


@router.delete("/{watch_id}", status_code=204, summary="관심종목 해제")
def remove_watch(watch_id: int, db: Session = Depends(get_db)):
    watch = db.get(Watch, watch_id)
    if watch is None:
        raise HTTPException(404, "존재하지 않는 관심종목입니다.")
    db.delete(watch)
    db.commit()
