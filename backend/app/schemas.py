"""API 응답 형태(Pydantic). /docs 에서 자동 문서로 보여요."""
from datetime import date, datetime
from typing import List

from pydantic import BaseModel, ConfigDict


class StockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    market: str
    sector: str | None
    price: float
    prev_close: float
    change_rate: float
    trade_value: float
    volume: int
    market_cap: float
    buy_ratio: int
    logo_text: str
    logo_color: str


class StockDetail(StockOut):
    day_low: float
    day_high: float
    week52_low: float
    week52_high: float
    value_rank: int  # 같은 시장 안에서의 거래대금 순위


class CandleOut(BaseModel):
    t: date
    o: float
    h: float
    l: float
    c: float
    v: int


class IndexOut(BaseModel):
    name: str
    value: float
    change: float
    change_rate: float
    series: List[float]


class NewsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source: str
    published_at: datetime
    sentiment: str


class InvestorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    individual: int
    foreign: int
    institution: int


class AnalysisOut(BaseModel):
    code: str
    direction: str  # up / down / flat
    question: str  # "왜 올랐을까?" 같은 제목
    headline: str
    reasons: List[str]
    mode: str  # rule: 규칙 기반, llm: LLM 연결 시
    news: List[NewsOut]


class OpinionOut(BaseModel):
    code: str
    price: float
    strong_buy: int
    buy: int
    hold: int
    sell: int
    strong_sell: int
    total: int
    score: float  # 0(적극매도) ~ 100(적극매수)
    label: str  # 적극매수 / 매수 / 중립 / 매도 / 적극매도
    buy_pct: float  # 매수 계열(적극매수+매수) 비중(%)
    target_avg: float
    target_high: float
    target_low: float
    upside_pct: float  # 평균 목표주가 대비 현재가 상승여력(%)
    updated: date


class RecommendedOut(StockOut):
    score: float
    label: str
    total: int
    volatility: float = 0.0


class InsightOut(BaseModel):
    """홈 카드용 요약."""
    pos52: float
    low52: float
    high52: float
    ret_1w: float | None
    ret_1m: float | None
    ret_3m: float | None
    op_label: str | None
    op_total: int


class PeriodOut(BaseModel):
    label: str
    pct: float | None


class SignalOut(BaseModel):
    key: str
    title: str
    status: str  # good / neutral / bad
    text: str


class SimulationOut(BaseModel):
    invested: int
    value: int
    pct: float


class HeatOut(BaseModel):
    volume_ratio: float
    value_rank: int
    buy_ratio: int


class Net5Out(BaseModel):
    individual: int
    foreign: int
    institution: int


class DashboardOut(BaseModel):
    code: str
    summary: List[str]
    signals: List[SignalOut]
    pos52: float
    low52: float
    high52: float
    periods: List[PeriodOut]
    simulation: SimulationOut
    heat: HeatOut
    net5: Net5Out
