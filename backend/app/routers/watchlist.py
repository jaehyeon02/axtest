"""관심 종목.

로그인 기능이 없으므로 브라우저가 만든 임시 ID(X-Client-Id 헤더)로 사용자를 구분합니다.
아무도 하트를 누르지 않으면 목록은 항상 비어 있어요.
"""
from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Stock, Watchlist
from ..schemas import StockOut

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


def client_id(x_client_id: str = Header(default="")) -> str:
    if not x_client_id or len(x_client_id) > 64:
        raise HTTPException(400, "X-Client-Id 헤더가 필요해요.")
    return x_client_id


@router.get("", response_model=List[StockOut])
def my_watchlist(cid: str = Depends(client_id), db: Session = Depends(get_db)):
    return (
        db.query(Stock).join(Watchlist, Watchlist.code == Stock.code)
        .filter(Watchlist.client_id == cid).order_by(Watchlist.created_at).all()
    )


@router.put("/{code}", status_code=204)
def add(code: str, cid: str = Depends(client_id), db: Session = Depends(get_db)):
    if not db.get(Stock, code):
        raise HTTPException(404, "종목을 찾을 수 없어요.")
    exists = db.query(Watchlist).filter_by(client_id=cid, code=code).first()
    if not exists:  # 이미 담겨 있어도 오류 없이 넘어갑니다.
        db.add(Watchlist(client_id=cid, code=code))
        db.commit()


@router.delete("/{code}", status_code=204)
def remove(code: str, cid: str = Depends(client_id), db: Session = Depends(get_db)):
    db.query(Watchlist).filter_by(client_id=cid, code=code).delete()
    db.commit()
