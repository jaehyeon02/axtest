from fastapi import APIRouter, Depends

from .. import service as S
from ..deps import get_dbx

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/status")
def status(db=Depends(get_dbx)):
    """데이터 출처(샘플/실데이터), 최신 시세일, 표별 행 수, 최근 수집 기록."""
    return S.status(db)
