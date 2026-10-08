"""데이터 상태: 지금 들어 있는 데이터가 샘플인지 실데이터인지, 마지막 수집은 언제인지."""
from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Company, Document, FinancialYear, IngestionLog, PriceDaily
from ..schemas import StatusOut

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/status", response_model=StatusOut)
def status(db: Session = Depends(get_db)):
    counts = {
        "company": db.scalar(select(func.count()).select_from(Company)),
        "price_daily": db.scalar(select(func.count()).select_from(PriceDaily)),
        "financial_year": db.scalar(select(func.count()).select_from(FinancialYear)),
        "filing": db.scalar(select(func.count()).select_from(Document).where(Document.doc_type == "filing")),
    }
    logs = db.scalars(select(IngestionLog).order_by(desc(IngestionLog.finished_at), desc(IngestionLog.log_id)).limit(8)).all()
    ok_sources = {l.source for l in logs if l.status == "ok"}
    real = ok_sources & {"pykrx", "opendart"}
    source = "+".join(sorted(real)) if real else ("sample" if ok_sources else "empty")
    return {
        "source": source, "is_sample": not real, "last_price_date": db.scalar(select(func.max(PriceDaily.trade_date))), "counts": counts,
        "recent": [{"job": l.job, "source": l.source, "status": l.status, "rows": l.row_count, "message": l.message, "at": l.finished_at.isoformat()} for l in logs],
    }
