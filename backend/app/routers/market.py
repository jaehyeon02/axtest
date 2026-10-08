import json
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MarketIndex
from ..schemas import IndexOut

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/indices", response_model=List[IndexOut])
def indices(db: Session = Depends(get_db)):
    """상단 지수 띠(코스피, 코스닥, 환율, 나스닥 …)."""
    rows = db.query(MarketIndex).order_by(MarketIndex.sort_order).all()
    return [
        IndexOut(
            name=r.name, value=r.value, change=r.change, change_rate=r.change_rate,
            series=json.loads(r.series),
        )
        for r in rows
    ]
