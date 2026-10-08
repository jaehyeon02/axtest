from sqlalchemy import insert, select, text

from datetime import datetime

from .models import Company, Document, FinancialYear, IngestionLog, PriceDaily, Sector
from .seed_data import generate

TABLES = [("sector", Sector), ("company", Company), ("price_daily", PriceDaily), ("financial_year", FinancialYear), ("document", Document)]


def seed(db):
    """회사 테이블이 비어 있을 때만 샘플 데이터를 넣어요. (이미 있으면 아무것도 하지 않아요.)"""
    if db.execute(select(Company.company_id).limit(1)).first():
        return
    data = generate()
    for key, model in TABLES:
        db.execute(insert(model), data[key])
    db.add(IngestionLog(job="sample", source="sample", status="ok", row_count=sum(len(v) for v in data.values()),
                        message="개발용 가상 샘플 데이터", finished_at=datetime.now()))
    db.commit()
    if db.bind.dialect.name == "postgresql":  # 직접 id를 넣었으니 PostgreSQL 의 번호표(시퀀스)를 맞춰 줘요.
        for table, pk in (("document", "doc_id"), ("company", "company_id"), ("sector", "sector_id"), ("price_daily", "price_id"), ("financial_year", "fin_id")):
            db.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', '{pk}'), (SELECT MAX({pk}) FROM {table}))"))
        db.commit()
