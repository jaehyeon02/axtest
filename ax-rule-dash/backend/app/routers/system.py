from fastapi import APIRouter, Depends

from .. import service as S
from ..deps import get_dbx

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/status")
def status(db=Depends(get_dbx)):
    """데이터 출처(샘플/실데이터), 최신 시세일, 표별 행 수, 최근 수집 기록."""
    return S.status(db)


@router.get("/dashboard")
def dashboard(db=Depends(get_dbx)):
    """종목 분석 대시보드: 시장 요약 + 업종 집계 + 전 종목 지표·종합 점수."""
    return S.dashboard(db)
