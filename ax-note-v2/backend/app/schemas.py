from datetime import date, datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Stance = Literal["pos", "neg", "neu"]


class CompanyOut(BaseModel):
    company_id: int
    code: str
    name: str
    market: str
    sector: str
    price: Optional[float] = None
    change_rate: float = 0.0
    trade_date: Optional[date] = None


class PriceOut(BaseModel):
    price_id: int
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class MonthlyOut(BaseModel):
    ym: str
    avg_close: float
    low: float
    high: float
    volume: float


class FinancialOut(BaseModel):
    fin_id: int
    fiscal_year: int
    revenue: float
    operating_profit: float
    net_income: Optional[float] = None
    op_margin: Optional[float] = None
    rev_growth: Optional[float] = None


class PeerOut(BaseModel):
    company_id: int
    code: str
    name: str
    fiscal_year: int
    revenue: float
    operating_profit: float
    op_margin: Optional[float] = None
    rev_growth: Optional[float] = None
    margin_rank: int
    growth_rank: int
    n: int
    avg_margin: Optional[float] = None
    avg_growth: Optional[float] = None


class AnalysisOut(BaseModel):
    trade_date: date
    close: float
    returns: dict[str, Optional[float]]
    ma120: Optional[float] = None
    ma120_gap: Optional[float] = None
    mdd: Optional[float] = None
    volatility_daily: Optional[float] = None
    volatility_annual: Optional[float] = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    doc_id: int
    company_id: int
    doc_type: str
    title: str
    body: str = ""
    source: str
    sentiment: str
    published_date: date
    rcept_no: Optional[str] = None
    url: Optional[str] = None
    user_added: bool = False  # 사용자가 직접 추가한 문서인지(수집 문서는 수정·삭제 불가)


class DocumentIn(BaseModel):
    """내 자료(기사·메모) 추가. 공시는 수집 스크립트만 넣을 수 있어요."""
    company_code: str
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=5000)
    source: str = Field(default="직접 입력", max_length=60)
    url: Optional[str] = Field(default=None, max_length=300, pattern=r"^https?://")
    sentiment: Stance = "neu"
    published_date: date


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    body: Optional[str] = Field(default=None, max_length=5000)
    source: Optional[str] = Field(default=None, min_length=1, max_length=60)
    url: Optional[str] = Field(default=None, max_length=300, pattern=r"^https?://")
    sentiment: Optional[Stance] = None
    published_date: Optional[date] = None


class EventOut(BaseModel):
    """급등락일과 그날 전후로 나온 문서"""
    price_id: int
    trade_date: date
    close: float
    prev_close: float
    ret_pct: float
    volume: int
    docs: List[DocumentOut]


class NoteIn(BaseModel):
    company_code: str
    title: str = Field(min_length=1, max_length=120)
    memo: str = Field(default="", max_length=5000)
    stance: Stance = "neu"


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    memo: Optional[str] = Field(default=None, max_length=5000)
    stance: Optional[Stance] = None


class EvidenceIn(BaseModel):
    doc_id: Optional[int] = None
    price_id: Optional[int] = None
    comment: str = Field(default="", max_length=300)


class EvidenceComment(BaseModel):
    comment: str = Field(max_length=300)


class EvidencePrice(BaseModel):
    price_id: int
    trade_date: date
    close: float
    ret_pct: Optional[float] = None


class EvidenceOut(BaseModel):
    evidence_id: int
    kind: Literal["document", "price"]
    comment: str
    document: Optional[DocumentOut] = None
    price: Optional[EvidencePrice] = None


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    note_id: int
    company_code: str
    company_name: str
    title: str
    memo: str
    stance: str
    created_at: datetime
    updated_at: datetime
    evidence: List[EvidenceOut] = []


class WatchOut(BaseModel):
    watch_id: int
    company: CompanyOut
    created_at: datetime


class StatusOut(BaseModel):
    source: str  # sample / pykrx+opendart / empty
    is_sample: bool
    last_price_date: Optional[date] = None
    counts: dict[str, int]
    recent: List[dict[str, Any]] = []
