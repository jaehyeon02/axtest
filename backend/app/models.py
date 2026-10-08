"""테이블 정의 (ERD).

stocks 1 ── N candles      (일봉)
stocks 1 ── N news         (뉴스)
stocks 1 ── N investors    (개인·외국인·기관 순매수)
stocks 1 ── N watchlist    (사용자별 관심 종목)
stocks 1 ── 1 consensus    (전문가 투자의견 집계)
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Stock(Base):
    __tablename__ = "stocks"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    market: Mapped[str] = mapped_column(String(2))  # kr: 국내, us: 해외
    sector: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    price: Mapped[float]  # 현재가(원)
    prev_close: Mapped[float]  # 전일 종가(원)
    change_rate: Mapped[float]  # 등락률(%)
    trade_value: Mapped[float]  # 거래대금(억원)
    volume: Mapped[int]  # 거래량(주)
    market_cap: Mapped[float]  # 시가총액(억원)
    buy_ratio: Mapped[int]  # 매수 체결 비율(%) 0~100
    logo_text: Mapped[str] = mapped_column(String(4))
    logo_color: Mapped[str] = mapped_column(String(9))


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (UniqueConstraint("code", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(ForeignKey("stocks.code"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[float]
    high: Mapped[float]
    low: Mapped[float]
    close: Mapped[float]
    volume: Mapped[int]


class MarketIndex(Base):
    __tablename__ = "market_indices"

    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    sort_order: Mapped[int]
    value: Mapped[float]
    change: Mapped[float]
    change_rate: Mapped[float]
    series: Mapped[str]  # 스파크라인용 값 목록(JSON 문자열)


class News(Base):
    __tablename__ = "news"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(ForeignKey("stocks.code"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(40))
    published_at: Mapped[datetime] = mapped_column(DateTime)
    sentiment: Mapped[str] = mapped_column(String(8))  # pos / neg / neu


class Investor(Base):
    __tablename__ = "investors"
    __table_args__ = (UniqueConstraint("code", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(ForeignKey("stocks.code"), index=True)
    day: Mapped[date] = mapped_column(Date)
    individual: Mapped[int]  # 개인 순매수(주)
    foreign: Mapped[int]  # 외국인 순매수(주)
    institution: Mapped[int]  # 기관 순매수(주)


class Watchlist(Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("client_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)  # 브라우저별 임시 ID(로그인 대신)
    code: Mapped[str] = mapped_column(ForeignKey("stocks.code"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Consensus(Base):
    """전문가(증권사 애널리스트) 투자의견 집계. 종목당 1행."""

    __tablename__ = "consensus"

    code: Mapped[str] = mapped_column(ForeignKey("stocks.code"), primary_key=True)
    strong_buy: Mapped[int]  # 적극매수 의견 수
    buy: Mapped[int]  # 매수
    hold: Mapped[int]  # 중립
    sell: Mapped[int]  # 매도
    strong_sell: Mapped[int]  # 적극매도
    target_avg: Mapped[float]  # 평균 목표주가(원)
    target_high: Mapped[float]
    target_low: Mapped[float]
    updated: Mapped[date] = mapped_column(Date)
