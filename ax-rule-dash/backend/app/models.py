"""테이블 정의. db/schema.sql 과 같은 구조예요 (서버가 켜질 때 create_all 로 만들어요)."""
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


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


class PriceDaily(Base):
    __tablename__ = "price_daily"
    __table_args__ = (
        UniqueConstraint("company_id", "trade_date", name="uq_price"),
        CheckConstraint("low <= open AND low <= close AND high >= open AND high >= close", name="ck_price"),
    )
    price_id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.company_id"))
    trade_date: Mapped[date] = mapped_column(Date)
    open: Mapped[float] = mapped_column(Numeric(14, 2))
    high: Mapped[float] = mapped_column(Numeric(14, 2))
    low: Mapped[float] = mapped_column(Numeric(14, 2))
    close: Mapped[float] = mapped_column(Numeric(14, 2))
    volume: Mapped[int] = mapped_column(BigInteger)


class FundamentalDaily(Base):
    __tablename__ = "fundamental_daily"
    __table_args__ = (UniqueConstraint("company_id", "trade_date", name="uq_fund"),)
    fund_id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.company_id"))
    trade_date: Mapped[date] = mapped_column(Date)
    per: Mapped[float | None] = mapped_column(Numeric(10, 2))
    pbr: Mapped[float | None] = mapped_column(Numeric(10, 2))
    eps: Mapped[float | None] = mapped_column(Numeric(14, 2))
    bps: Mapped[float | None] = mapped_column(Numeric(14, 2))


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


class Rule(Base):
    __tablename__ = "rule"
    __table_args__ = (
        UniqueConstraint("client_id", "name", name="uq_rule_name"),
        CheckConstraint("entry_type IN ('ma_cross', 'dip_buy', 'breakout')", name="ck_rule_type"),
        CheckConstraint("entry_param > 0", name="ck_rule_param"),
        CheckConstraint("take_profit_pct > 0", name="ck_rule_tp"),
        CheckConstraint("stop_loss_pct > 0", name="ck_rule_sl"),
        CheckConstraint("max_hold_days BETWEEN 1 AND 250", name="ck_rule_hold"),
        Index("ix_rule_client", "client_id", "updated_at"),
    )
    rule_id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(60))
    entry_type: Mapped[str] = mapped_column(String(12))
    entry_param: Mapped[float] = mapped_column(Numeric(6, 2))
    take_profit_pct: Mapped[float] = mapped_column(Numeric(6, 2))
    stop_loss_pct: Mapped[float] = mapped_column(Numeric(6, 2))
    max_hold_days: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class BacktestRun(Base):
    __tablename__ = "backtest_run"
    __table_args__ = (
        CheckConstraint("trade_count >= 0", name="ck_run_n"),
        CheckConstraint("win_count >= 0 AND win_count <= trade_count", name="ck_run_win"),
        Index("ix_run_rule", "rule_id", "company_id"),
    )
    run_id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rule.rule_id", ondelete="CASCADE"))
    company_id: Mapped[int] = mapped_column(ForeignKey("company.company_id"))
    rule_text: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    trade_count: Mapped[int]
    win_count: Mapped[int]
    avg_return: Mapped[float | None] = mapped_column(Numeric(10, 2))
    total_return: Mapped[float | None] = mapped_column(Numeric(10, 2))
    mdd: Mapped[float | None] = mapped_column(Numeric(10, 2))
    benchmark_return: Mapped[float | None] = mapped_column(Numeric(10, 2))
    avg_hold_days: Mapped[float | None] = mapped_column(Numeric(8, 1))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class BacktestTrade(Base):
    __tablename__ = "backtest_trade"
    __table_args__ = (
        CheckConstraint("exit_reason IN ('tp', 'sl', 'time', 'end')", name="ck_bt_reason"),
        CheckConstraint("hold_days >= 0", name="ck_bt_hold"),
        CheckConstraint("exit_date >= entry_date", name="ck_bt_dates"),
        Index("ix_bt_run", "run_id"),
    )
    bt_id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_run.run_id", ondelete="CASCADE"))
    entry_date: Mapped[date] = mapped_column(Date)
    entry_price: Mapped[float] = mapped_column(Numeric(14, 2))
    exit_date: Mapped[date] = mapped_column(Date)
    exit_price: Mapped[float] = mapped_column(Numeric(14, 2))
    exit_reason: Mapped[str] = mapped_column(String(8))
    return_pct: Mapped[float] = mapped_column(Numeric(10, 2))
    hold_days: Mapped[int]


class Account(Base):
    __tablename__ = "account"
    __table_args__ = (
        UniqueConstraint("client_id", "name", name="uq_account_name"),
        CheckConstraint("initial_cash > 0", name="ck_acc_initial"),
        CheckConstraint("cash >= 0", name="ck_acc_cash"),  # 잔고 부족 매수를 DB 수준에서 막아요
        Index("ix_account_client", "client_id"),
    )
    account_id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(40))
    initial_cash: Mapped[float] = mapped_column(Numeric(16, 0))
    cash: Mapped[float] = mapped_column(Numeric(16, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Trade(Base):
    __tablename__ = "trade"
    __table_args__ = (
        CheckConstraint("side IN ('buy', 'sell')", name="ck_trade_side"),
        CheckConstraint("price > 0", name="ck_trade_price"),
        CheckConstraint("qty > 0", name="ck_trade_qty"),
        CheckConstraint("fee >= 0", name="ck_trade_fee"),
        Index("ix_trade_account", "account_id", "trade_date", "trade_id"),
        Index("ix_trade_rule", "rule_id"),
    )
    trade_id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.account_id", ondelete="CASCADE"))
    company_id: Mapped[int] = mapped_column(ForeignKey("company.company_id"))
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("rule.rule_id", ondelete="SET NULL"))
    side: Mapped[str] = mapped_column(String(4))
    trade_date: Mapped[date] = mapped_column(Date)
    price: Mapped[float] = mapped_column(Numeric(14, 2))
    qty: Mapped[int]
    fee: Mapped[float] = mapped_column(Numeric(14, 2))
    memo: Mapped[str] = mapped_column(String(200), default="")


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
