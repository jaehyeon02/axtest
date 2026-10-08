from fastapi import APIRouter, Depends, Response

from .. import service as S
from ..deps import client_id, get_dbx
from ..schemas import BacktestIn, RuleIn, RuleUpdate

router = APIRouter(prefix="/api", tags=["rules"])


@router.get("/rules")
def list_rules(cid: str = Depends(client_id), db=Depends(get_dbx)):
    return S.list_rules(db, cid)


@router.post("/rules", status_code=201)
def create_rule(body: RuleIn, cid: str = Depends(client_id), db=Depends(get_dbx)):
    return S.create_rule(db, cid, body.model_dump())


@router.get("/rules/{rule_id}")
def get_rule(rule_id: int, cid: str = Depends(client_id), db=Depends(get_dbx)):
    return S.rule_detail(db, cid, rule_id)


@router.put("/rules/{rule_id}")
def update_rule(rule_id: int, body: RuleUpdate, cid: str = Depends(client_id), db=Depends(get_dbx)):
    return S.update_rule(db, cid, rule_id, body.model_dump(exclude_unset=True))


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, cid: str = Depends(client_id), db=Depends(get_dbx)):
    S.delete_rule(db, cid, rule_id)
    return Response(status_code=204)


@router.get("/rules/{rule_id}/signals")
def rule_signals(rule_id: int, cid: str = Depends(client_id), db=Depends(get_dbx)):
    """이 규칙의 진입 조건이 가장 최근 거래일에 맞은 종목."""
    return S.rule_signals(db, cid, rule_id)


@router.get("/rules/{rule_id}/report")
def rule_report(rule_id: int, cid: str = Depends(client_id), db=Depends(get_dbx)):
    """백테스트 성적 vs 실제 모의투자 성적."""
    return S.rule_report(db, cid, rule_id)


@router.get("/rules/{rule_id}/backtests")
def list_runs(rule_id: int, cid: str = Depends(client_id), db=Depends(get_dbx)):
    return S.list_runs(db, cid, rule_id)


@router.post("/rules/{rule_id}/backtests", status_code=201)
def run_backtest(rule_id: int, body: BacktestIn, cid: str = Depends(client_id), db=Depends(get_dbx)):
    return S.run_backtest(db, cid, rule_id, body.company_code, body.period)


@router.get("/backtests/{run_id}")
def get_run(run_id: int, cid: str = Depends(client_id), db=Depends(get_dbx)):
    return S.get_run(db, cid, run_id)


@router.delete("/backtests/{run_id}", status_code=204)
def delete_run(run_id: int, cid: str = Depends(client_id), db=Depends(get_dbx)):
    S.delete_run(db, cid, run_id)
    return Response(status_code=204)


@router.get("/signals")
def all_signals(cid: str = Depends(client_id), db=Depends(get_dbx)):
    """내 모든 규칙 중 오늘 진입 조건이 맞은 종목들."""
    return S.all_signals(db, cid)
