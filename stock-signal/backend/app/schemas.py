"""요청/응답 데이터 형식 (Pydantic). 잘못된 입력은 여기서 422 로 걸러진다."""
import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# ---------- 시장 / 업종 ----------
class MarketOut(ORMModel):
    market_id: int
    name: str


class SectorCreate(ORMModel):
    name: str = Field(min_length=1, max_length=50)


class SectorOut(ORMModel):
    sector_id: int
    name: str


# ---------- 종목 ----------
class CompanyCreate(ORMModel):
    code: str = Field(pattern=r"^[0-9A-Z]{6}$", description="종목코드 6자리 (예: 005930)")
    name: str = Field(min_length=1, max_length=100)
    market_id: int
    sector_id: int | None = None


class CompanyUpdate(ORMModel):
    """종목코드는 바꾸지 않는다. 보낸 항목만 수정된다."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    market_id: int | None = None
    sector_id: int | None = None


class CompanyOut(ORMModel):
    company_id: int
    code: str
    name: str
    market_name: str
    sector_name: str | None = None


# ---------- 일별 시세 ----------
class PriceCreate(ORMModel):
    company_id: int
    trade_date: dt.date
    open_price: int = Field(ge=0)
    high_price: int = Field(ge=0)
    low_price: int = Field(ge=0)
    close_price: int = Field(ge=0)
    volume: int = Field(ge=0)

    @model_validator(mode="after")
    def check_high_low(self):
        if self.high_price < self.low_price:
            raise ValueError("고가(high_price)는 저가(low_price)보다 작을 수 없습니다.")
        return self


class PriceUpdate(ORMModel):
    """보낸 항목만 수정된다. (종목/날짜는 바꿀 수 없음 - 잘못 넣었다면 삭제 후 다시 등록)"""

    open_price: int | None = Field(default=None, ge=0)
    high_price: int | None = Field(default=None, ge=0)
    low_price: int | None = Field(default=None, ge=0)
    close_price: int | None = Field(default=None, ge=0)
    volume: int | None = Field(default=None, ge=0)


class PriceOut(ORMModel):
    price_id: int
    company_id: int
    trade_date: dt.date
    open_price: int
    high_price: int
    low_price: int
    close_price: int
    volume: int


# ---------- 회원 ----------
class MemberCreate(ORMModel):
    nickname: str = Field(min_length=1, max_length=30)


class MemberOut(ORMModel):
    member_id: int
    nickname: str
    created_at: dt.datetime


# ---------- 관심종목 ----------
class WatchCreate(ORMModel):
    member_id: int
    company_id: int


class WatchOut(ORMModel):
    watch_id: int
    member_id: int
    company_id: int
    created_at: dt.datetime


# ---------- 모의 거래 ----------
class TradeCreate(ORMModel):
    member_id: int
    company_id: int
    trade_date: dt.date
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)
    price: int = Field(ge=0)
    memo: str | None = Field(default=None, max_length=200)


class TradeUpdate(ORMModel):
    """메모만 고칠 수 있다. 수량·가격을 바꾸면 보유 계산이 어긋나므로, 잘못 넣었다면 삭제 후 다시 등록한다."""

    memo: str | None = Field(default=None, max_length=200)


class TradeOut(ORMModel):
    trade_id: int
    member_id: int
    company_id: int
    trade_date: dt.date
    side: str
    quantity: int
    price: int
    memo: str | None
    created_at: dt.datetime
