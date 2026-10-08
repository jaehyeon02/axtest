from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import queries
from app.db import get_db
from app.models import Company, Member, PaperTrade
from app.schemas import TradeCreate, TradeOut, TradeUpdate

router = APIRouter(prefix="/trades", tags=["모의 거래"])


def _get_trade_or_404(db: Session, trade_id: int) -> PaperTrade:
    trade = db.get(PaperTrade, trade_id)
    if trade is None:
        raise HTTPException(404, "존재하지 않는 거래입니다.")
    return trade


@router.get("", response_model=list[TradeOut], summary="모의 거래 목록 (최신순)")
def list_trades(
    member_id: int | None = None,
    company_id: int | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(PaperTrade).order_by(PaperTrade.trade_date.desc(), PaperTrade.trade_id.desc()).limit(limit)
    if member_id is not None:
        stmt = stmt.where(PaperTrade.member_id == member_id)
    if company_id is not None:
        stmt = stmt.where(PaperTrade.company_id == company_id)
    return db.scalars(stmt).all()


@router.get("/portfolio", summary="모의 포트폴리오 (보유 수량·평균 매수가·평가손익을 SQL 로 계산)")
def portfolio(member_id: int, db: Session = Depends(get_db)):
    if db.get(Member, member_id) is None:
        raise HTTPException(404, "존재하지 않는 회원입니다.")
    rows = [dict(r) for r in db.execute(text(queries.PORTFOLIO), {"member_id": member_id}).mappings().all()]
    # 합계는 위 행들을 더하기만 한다 (종가가 없는 종목은 평가에서 제외)
    priced = [r for r in rows if r["market_value"] is not None]
    cost = sum(float(r["avg_cost"]) * r["qty"] for r in priced)
    value = sum(r["market_value"] for r in priced)
    return {
        "holdings": rows,
        "total": {
            "market_value": value,
            "pnl": round(value - cost),
            "pnl_pct": round((value / cost - 1) * 100, 2) if cost else None,
        },
    }


@router.get("/{trade_id}", response_model=TradeOut, summary="거래 1건 조회")
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    return _get_trade_or_404(db, trade_id)


@router.post("", response_model=TradeOut, status_code=201, summary="모의 거래 등록 (매도는 보유 수량까지만)")
def create_trade(body: TradeCreate, db: Session = Depends(get_db)):
    if db.get(Member, body.member_id) is None:
        raise HTTPException(404, "존재하지 않는 회원입니다.")
    if db.get(Company, body.company_id) is None:
        raise HTTPException(404, "존재하지 않는 종목입니다.")
    if body.side == "SELL":
        held = db.execute(
            text(queries.HELD_QTY), {"member_id": body.member_id, "company_id": body.company_id}
        ).scalar_one()
        if body.quantity > held:
            raise HTTPException(422, f"보유 수량({held}주)보다 많이 팔 수 없습니다.")
    trade = PaperTrade(**body.model_dump())
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


@router.put("/{trade_id}", response_model=TradeOut, summary="거래 메모 수정")
def update_trade(trade_id: int, body: TradeUpdate, db: Session = Depends(get_db)):
    trade = _get_trade_or_404(db, trade_id)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "수정할 항목이 없습니다.")
    trade.memo = changes["memo"]
    db.commit()
    db.refresh(trade)
    return trade


@router.delete("/{trade_id}", status_code=204, summary="거래 삭제 (매수를 지워 보유가 음수가 되면 거부)")
def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = _get_trade_or_404(db, trade_id)
    if trade.side == "BUY":
        held = db.execute(
            text(queries.HELD_QTY), {"member_id": trade.member_id, "company_id": trade.company_id}
        ).scalar_one()
        if held - trade.quantity < 0:
            raise HTTPException(409, "이 매수를 지우면 이미 매도한 수량보다 보유가 적어집니다. 매도 기록부터 지우세요.")
    db.delete(trade)
    db.commit()
