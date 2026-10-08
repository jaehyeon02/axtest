"""테이블 정의. db/schema.sql 과 같은 구조예요."""
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from sqlalchemy import BigInteger


class Sector(Base):
    __tablename__ = "sector"
    sector_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)


class Company(Base):
    __tablename__ = "company"
    company_id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True)
    name: Mapped[str] = mapped_column(String(60))
    market: Mapped[str] = mapped_column(String(10))
    sector_id: Mapped[int] = mapped_column(ForeignKey("sector.sector_id"))
    corp_code: Mapped[str | None] = mapped_column(String(8))
    sector: Mapped[Sector] = relationship()


class PriceDaily(Base):
    __tablename__ = "price_daily"
    __table_args__ = (
        UniqueConstraint("company_id", "trade_date", name="uq_price"),
        CheckConstraint("low <= open AND low <= close AND high >= open AND high >= close", name="ck_price"),
        Index("ix_price_company_date", "company_id", "trade_date"),
    )
    price_id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.company_id"))
    trade_date: Mapped[date] = mapped_column(Date)
    open: Mapped[float] = mapped_column(Numeric(14, 2))
    high: Mapped[float] = mapped_column(Numeric(14, 2))
    low: Mapped[float] = mapped_column(Numeric(14, 2))
    close: Mapped[float] = mapped_column(Numeric(14, 2))
    volume: Mapped[int] = mapped_column(BigInteger)


class FinancialYear(Base):
    __tablename__ = "financial_year"
    __table_args__ = (
        UniqueConstraint("company_id", "fiscal_year", name="uq_fin"),
        CheckConstraint("fiscal_year BETWEEN 1990 AND 2100", name="ck_fin_year"),
    )
    fin_id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.company_id"))
    fiscal_year: Mapped[int]
    revenue: Mapped[float] = mapped_column(Numeric(16, 1))
    operating_profit: Mapped[float] = mapped_column(Numeric(16, 1))
    net_income: Mapped[float | None] = mapped_column(Numeric(16, 1))


class Document(Base):
    __tablename__ = "document"
    __table_args__ = (
        CheckConstraint("doc_type IN ('news', 'filing')", name="ck_doc_type"),
        CheckConstraint("sentiment IN ('pos', 'neg', 'neu')", name="ck_doc_sentiment"),
        CheckConstraint(
            "(doc_type = 'filing' AND created_by IS NULL) OR (doc_type = 'news' AND created_by IS NOT NULL)", name="ck_doc_owner"
        ),
        Index("ix_doc_company_date", "company_id", "published_date"),
        Index("ux_doc_rcept", "rcept_no", unique=True),
    )
    doc_id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.company_id"))
    doc_type: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(60))
    sentiment: Mapped[str] = mapped_column(String(8), default="neu")
    published_date: Mapped[date] = mapped_column(Date)
    rcept_no: Mapped[str | None] = mapped_column(String(20))
    url: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[str | None] = mapped_column(String(64))


class Note(Base):
    __tablename__ = "note"
    __table_args__ = (
        CheckConstraint("stance IN ('pos', 'neg', 'neu')", name="ck_note_stance"),
        Index("ix_note_client", "client_id", "updated_at"),
    )
    note_id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64))
    company_id: Mapped[int] = mapped_column(ForeignKey("company.company_id"))
    title: Mapped[str] = mapped_column(String(120))
    memo: Mapped[str] = mapped_column(Text, default="")
    stance: Mapped[str] = mapped_column(String(8), default="neu")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    company: Mapped[Company] = relationship()
    evidence: Mapped[list["NoteEvidence"]] = relationship(back_populates="note", cascade="all, delete-orphan", order_by="NoteEvidence.evidence_id")


class NoteEvidence(Base):
    __tablename__ = "note_evidence"
    __table_args__ = (
        CheckConstraint(
            "(doc_id IS NOT NULL AND price_id IS NULL) OR (doc_id IS NULL AND price_id IS NOT NULL)", name="ck_evidence_one"
        ),
        Index("ix_evidence_note", "note_id"),
    )
    evidence_id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("note.note_id", ondelete="CASCADE"))
    doc_id: Mapped[int | None] = mapped_column(ForeignKey("document.doc_id", ondelete="CASCADE"))
    price_id: Mapped[int | None] = mapped_column(ForeignKey("price_daily.price_id", ondelete="CASCADE"))
    comment: Mapped[str] = mapped_column(String(300), default="")
    note: Mapped[Note] = relationship(back_populates="evidence")
    document: Mapped[Document | None] = relationship()
    price: Mapped[PriceDaily | None] = relationship()


class Watchlist(Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("client_id", "company_id", name="uq_watch"),)
    watch_id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64))
    company_id: Mapped[int] = mapped_column(ForeignKey("company.company_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    company: Mapped[Company] = relationship()


class IngestionLog(Base):
    __tablename__ = "ingestion_log"
    __table_args__ = (CheckConstraint("status IN ('ok', 'fail')", name="ck_log_status"),)
    log_id: Mapped[int] = mapped_column(primary_key=True)
    job: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10))
    row_count: Mapped[int] = mapped_column(default=0)
    message: Mapped[str] = mapped_column(String(300), default="")
    finished_at: Mapped[datetime] = mapped_column(DateTime)
