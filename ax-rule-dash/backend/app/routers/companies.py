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


@router.get("/{code}/analysis")
def analysis(code: str, db=Depends(get_dbx)):
    """수익률·120일선 괴리·거래량 배수·최대 낙폭·변동성·PER/PBR + 종합 점수 구성."""
    return S.company_analysis(db, code)


@router.get("/{code}/fundamentals")
def fundamentals(code: str, days: int = Query(365, ge=5, le=800), db=Depends(get_dbx)):
    """일별 PER·PBR·EPS·BPS."""
    return S.company_fundamentals(db, code, days)


@router.get("/{code}/financials")
def financials(code: str, db=Depends(get_dbx)):
    """최근 5개년 매출·영업이익·영업이익률·매출 성장률."""
    return S.company_financials(db, code)


@router.get("/{code}/peers")
def peers(code: str, db=Depends(get_dbx)):
    """같은 업종 회사들과 영업이익률·매출 성장률 순위 비교."""
    return S.company_peers(db, code)


@router.get("/{code}/monthly")
def monthly(code: str, db=Depends(get_dbx)):
    return S.company_monthly(db, code)
