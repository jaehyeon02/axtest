from fastapi import APIRouter, Depends, Response

from .. import service as S
from ..deps import client_id, get_dbx
from ..schemas import AccountIn, AccountUpdate, TradeIn, TradeUpdate

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("")
def list_accounts(cid: str = Depends(client_id), db=Depends(get_dbx)):
    return S.list_accounts(db, cid)


@router.post("", status_code=201)
def create_account(body: AccountIn, cid: str = Depends(client_id), db=Depends(get_dbx)):
    return S.create_account(db, cid, body.name, body.initial_cash)


@router.get("/{account_id}")
def account_detail(account_id: int, cid: str = Depends(client_id), db=Depends(get_dbx)):
    """현금·보유 종목·평가손익·실현손익 + 장부 감사 결과."""
    return S.account_detail(db, cid, account_id)


@router.put("/{account_id}")
def rename_account(account_id: int, body: AccountUpdate, cid: str = Depends(client_id), db=Depends(get_dbx)):
    return S.rename_account(db, cid, account_id, body.name)


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int, cid: str = Depends(client_id), db=Depends(get_dbx)):
    S.delete_account(db, cid, account_id)
    return Response(status_code=204)


@router.get("/{account_id}/trades")
def list_trades(account_id: int, cid: str = Depends(client_id), db=Depends(get_dbx)):
    return S.list_trades(db, cid, account_id)


@router.post("/{account_id}/trades", status_code=201)
def create_trade(account_id: int, body: TradeIn, cid: str = Depends(client_id), db=Depends(get_dbx)):
    """가격은 그날 종가로 서버가 채워요. 잔고·보유 수량이 안 맞으면 409."""
    return S.create_trade(db, cid, account_id, body.model_dump())


@router.put("/{account_id}/trades/{trade_id}")
def update_trade(account_id: int, trade_id: int, body: TradeUpdate, cid: str = Depends(client_id), db=Depends(get_dbx)):
    return S.update_trade(db, cid, account_id, trade_id, body.model_dump(exclude_unset=True))


@router.delete("/{account_id}/trades/{trade_id}", status_code=204)
def delete_trade(account_id: int, trade_id: int, cid: str = Depends(client_id), db=Depends(get_dbx)):
    S.delete_trade(db, cid, account_id, trade_id)
    return Response(status_code=204)
