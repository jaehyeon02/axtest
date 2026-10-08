from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Company, Market, Sector
from app.schemas import (
    CompanyCreate,
    CompanyOut,
    CompanyUpdate,
    MarketOut,
    SectorCreate,
    SectorOut,
)

router = APIRouter(tags=["종목"])


def _get_company_or_404(db: Session, company_id: int) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(404, "존재하지 않는 종목입니다.")
    return company


@router.get("/markets", response_model=list[MarketOut], summary="시장 목록")
def list_markets(db: Session = Depends(get_db)):
    return db.scalars(select(Market).order_by(Market.market_id)).all()


@router.get("/sectors", response_model=list[SectorOut], summary="업종 목록")
def list_sectors(db: Session = Depends(get_db)):
    return db.scalars(select(Sector).order_by(Sector.name)).all()


@router.post("/sectors", response_model=SectorOut, status_code=201, summary="업종 등록")
def create_sector(body: SectorCreate, db: Session = Depends(get_db)):
    sector = Sector(name=body.name)
    db.add(sector)
    db.commit()  # 이름이 중복이면 IntegrityError → 409 (errors.py)
    db.refresh(sector)
    return sector


@router.get("/companies", response_model=list[CompanyOut], summary="종목 목록/검색")
def list_companies(
    q: str | None = Query(None, description="종목명에 포함된 글자"),
    market_id: int | None = None,
    sector_id: int | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Company).order_by(Company.code).limit(limit).offset(offset)
    if q:
        stmt = stmt.where(Company.name.contains(q))
    if market_id is not None:
        stmt = stmt.where(Company.market_id == market_id)
    if sector_id is not None:
        stmt = stmt.where(Company.sector_id == sector_id)
    return db.scalars(stmt).unique().all()  # joined eager loading 사용 시 unique() 필요


@router.get("/companies/{company_id}", response_model=CompanyOut, summary="종목 상세")
def get_company(company_id: int, db: Session = Depends(get_db)):
    return _get_company_or_404(db, company_id)


@router.post("/companies", response_model=CompanyOut, status_code=201, summary="종목 등록")
def create_company(body: CompanyCreate, db: Session = Depends(get_db)):
    company = Company(**body.model_dump())
    db.add(company)
    db.commit()  # 코드 중복 → 409, 없는 market_id/sector_id → 409
    return _get_company_or_404(db, company.company_id)


@router.put("/companies/{company_id}", response_model=CompanyOut, summary="종목 수정")
def update_company(company_id: int, body: CompanyUpdate, db: Session = Depends(get_db)):
    company = _get_company_or_404(db, company_id)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "수정할 항목이 없습니다.")
    for key, value in changes.items():
        setattr(company, key, value)
    db.commit()
    db.expire_all()  # 시장/업종이 바뀌었을 수 있으니 관계를 다시 읽는다
    return _get_company_or_404(db, company_id)


@router.delete("/companies/{company_id}", status_code=204, summary="종목 삭제 (시세·재무·메모도 함께 삭제)")
def delete_company(company_id: int, db: Session = Depends(get_db)):
    company = _get_company_or_404(db, company_id)
    db.delete(company)  # 하위 데이터는 DB 의 ON DELETE CASCADE 가 지운다
    db.commit()
