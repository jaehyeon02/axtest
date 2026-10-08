"""SQLAlchemy 모델 - sql/01_schema.sql 의 테이블과 1:1 로 대응한다.

테이블 생성은 SQL 스크립트가 담당하므로 create_all() 은 사용하지 않는다.
"""
import datetime as dt

from sqlalchemy import (
    CHAR,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Market(Base):
    __tablename__ = "markets"

    market_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True)


class Sector(Base):
    __tablename__ = "sectors"

    sector_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)


class Company(Base):
    __tablename__ = "companies"

    company_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(CHAR(6), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.market_id"))
    sector_id: Mapped[int | None] = mapped_column(ForeignKey("sectors.sector_id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    market: Mapped[Market] = relationship(lazy="joined")
    sector: Mapped[Sector | None] = relationship(lazy="joined")

    @property
    def market_name(self) -> str:
        return self.market.name

    @property
    def sector_name(self) -> str | None:
        return self.sector.name if self.sector else None


class DailyPrice(Base):
    __tablename__ = "daily_prices"

    price_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.company_id"))
    trade_date: Mapped[dt.date] = mapped_column(Date)
    open_price: Mapped[int] = mapped_column(Integer)
    high_price: Mapped[int] = mapped_column(Integer)
    low_price: Mapped[int] = mapped_column(Integer)
    close_price: Mapped[int] = mapped_column(Integer)
    volume: Mapped[int] = mapped_column(BigInteger)


class Member(Base):
    __tablename__ = "members"

    member_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nickname: Mapped[str] = mapped_column(String(30), unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class Watch(Base):
    __tablename__ = "watchlist"

    watch_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.member_id"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.company_id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    trade_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.member_id"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.company_id"))
    trade_date: Mapped[dt.date] = mapped_column(Date)
    side: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Integer)
    memo: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
