"""요청 본문 모양. 값의 범위·형식 검사는 service.py 가 한국어 메시지로 해서, 여기서는 느슨하게 받아요.
(응답은 service 가 돌려주는 딕셔너리를 그대로 JSON 으로 내보내요.)"""
from typing import Any, Optional

from pydantic import BaseModel


class RuleIn(BaseModel):
    name: str
    entry_type: str
    entry_param: Any
    take_profit_pct: Any
    stop_loss_pct: Any
    max_hold_days: Any


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    entry_type: Optional[str] = None
    entry_param: Optional[Any] = None
    take_profit_pct: Optional[Any] = None
    stop_loss_pct: Optional[Any] = None
    max_hold_days: Optional[Any] = None


class BacktestIn(BaseModel):
    company_code: str
    period: str = "1y"  # 6m | 1y | all


class AccountIn(BaseModel):
    name: str
    initial_cash: Any = 10_000_000


class AccountUpdate(BaseModel):
    name: str


class TradeIn(BaseModel):
    code: str
    side: str  # buy | sell
    trade_date: str
    qty: Any
    rule_id: Optional[int] = None
    memo: str = ""


class TradeUpdate(BaseModel):
    memo: Optional[str] = None
    rule_id: Optional[int] = None
