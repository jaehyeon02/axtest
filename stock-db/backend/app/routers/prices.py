import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Company, DailyPrice
from app.schemas import PriceCreate, PriceOut, PriceUpdate

router = APIRouter(prefix="/prices", tags=["일별 시세"])


def _get_price_or_404(db: Session, price_id: int) -> DailyPrice:
    price = db.get(DailyPrice, price_id)
    if price is None:
        raise HTTPException(404, "존재하지 않는 시세 데이터입니다.")
    return price


@router.get("", response_model=list[PriceOut], summary="시세 조회 (최신 날짜 순)")
def list_prices(
    code: str | None = Query(None, description="종목코드 (예: 005930)"),
    start: dt.date | None = None,
    end: dt.date | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(DailyPrice).order_by(DailyPrice.trade_date.desc(), DailyPrice.price_id)
    if code:
        stmt = stmt.join(Company, Company.company_id == DailyPrice.company_id).where(Company.code == code)
    if start:
        stmt = stmt.where(DailyPrice.trade_date >= start)
    if end:
        stmt = stmt.where(DailyPrice.trade_date <= end)
    return db.scalars(stmt.limit(limit).offset(offset)).all()


@router.get("/{price_id}", response_model=PriceOut, summary="시세 1건 조회")
def get_price(price_id: int, db: Session = Depends(get_db)):
    return _get_price_or_404(db, price_id)


@router.post("", response_model=PriceOut, status_code=201, summary="시세 등록")
def create_price(body: PriceCreate, db: Session = Depends(get_db)):
    if db.get(Company, body.company_id) is None:
        raise HTTPException(404, "존재하지 않는 종목입니다.")
    price = DailyPrice(**body.model_dump())
    db.add(price)
    db.commit()  # 같은 종목/날짜가 이미 있으면 409
    db.refresh(price)
    return price


@router.put("/{price_id}", response_model=PriceOut, summary="시세 수정 (보낸 항목만)")
def update_price(price_id: int, body: PriceUpdate, db: Session = Depends(get_db)):
    price = _get_price_or_404(db, price_id)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "수정할 항목이 없습니다.")
    for key, value in changes.items():
        setattr(price, key, value)
    if price.high_price < price.low_price:
        raise HTTPException(422, "고가(high_price)는 저가(low_price)보다 작을 수 없습니다.")
    db.commit()
    db.refresh(price)
    return price


@router.delete("/{price_id}", status_code=204, summary="시세 삭제")
def delete_price(price_id: int, db: Session = Depends(get_db)):
    price = _get_price_or_404(db, price_id)
    db.delete(price)
    db.commit()
