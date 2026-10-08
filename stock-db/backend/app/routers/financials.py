from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Company, FinancialStatement
from app.schemas import FinancialOut

router = APIRouter(prefix="/financials", tags=["재무"])


@router.get("", response_model=list[FinancialOut], summary="연도별 재무 조회 (OpenDART 적재 데이터)")
def list_financials(
    code: str | None = Query(None, description="종목코드"),
    year: int | None = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db),
):
    stmt = select(FinancialStatement).order_by(FinancialStatement.company_id, FinancialStatement.fiscal_year)
    if code:
        stmt = stmt.join(Company, Company.company_id == FinancialStatement.company_id).where(Company.code == code)
    if year:
        stmt = stmt.where(FinancialStatement.fiscal_year == year)
    return db.scalars(stmt).all()
