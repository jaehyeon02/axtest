from fastapi import APIRouter, Depends, Query

from .. import service as S
from ..deps import client_id, get_dbx

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("")
def list_companies(q: str = Query("", max_length=40), db=Depends(get_dbx)):
    """종목 목록·검색(이름 또는 코드) + 최신가·등락률."""
    return S.list_companies(db, q)


@router.get("/{code}")
def company_detail(code: str, db=Depends(get_dbx)):
    return S.company_detail(db, code)


@router.get("/{code}/prices")
def prices(code: str, days: int = Query(365, ge=5, le=800), db=Depends(get_dbx)):
    return S.prices(db, code, days)


@router.get("/{code}/my-trades")
def my_trades(code: str, cid: str = Depends(client_id), db=Depends(get_dbx)):
    """이 종목에 대한 내 거래(모든 내 계좌). 차트에 표시해요."""
    return S.my_trades_for_company(db, cid, code)
