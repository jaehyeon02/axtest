"""모의투자 장부 계산. 거래 목록을 처음부터 다시 훑어(replay) 현금·보유·실현손익을 구해요.

같은 함수가 세 군데에서 쓰여요: 거래를 넣을 때(규칙 위반 검사), 거래를 지울 때(이후 거래가 깨지지 않는지 검사),
계좌 화면(평균단가·실현손익). 평균단가법: 사면 (수수료 포함) 원가에 더하고, 팔면 평균단가만큼 원가에서 덜어내요.
"""


class LedgerError(Exception):
    def __init__(self, message: str, trade_id=None):
        super().__init__(message)
        self.trade_id = trade_id


def replay(trades: list, initial_cash: float) -> dict:
    """trades: (trade_date, trade_id) 순서로 정렬된 거래들.  잔고·수량이 마이너스가 되면 LedgerError."""
    cash = float(initial_cash)
    pos, realized = {}, []
    for t in sorted(trades, key=lambda x: (str(x["trade_date"])[:10], x["trade_id"])):
        cid, q, p, fee = t["company_id"], int(t["qty"]), float(t["price"]), float(t["fee"])
        h = pos.setdefault(cid, {"qty": 0, "cost": 0.0})
        amount = round(p * q, 2)
        if t["side"] == "buy":
            cash = round(cash - amount - fee, 2)
            if cash < 0:
                raise LedgerError(f"{str(t['trade_date'])[:10]} 매수 때 현금이 {-cash:,.0f}원 모자라요.", t["trade_id"])
            h["qty"] += q
            h["cost"] += amount + fee
        else:
            if q > h["qty"]:
                raise LedgerError(f"{str(t['trade_date'])[:10]} 매도 때 보유 수량({h['qty']}주)보다 많이 팔 수 없어요.", t["trade_id"])
            avg = h["cost"] / h["qty"]
            cash = round(cash + amount - fee, 2)
            pnl = amount - fee - avg * q
            realized.append({"trade_id": t["trade_id"], "company_id": cid, "rule_id": t.get("rule_id"), "trade_date": str(t["trade_date"])[:10],
                             "qty": q, "avg_cost": round(avg, 2), "price": p, "pnl": round(pnl, 2),
                             "return_pct": round(pnl / (avg * q) * 100, 2)})
            h["qty"] -= q
            h["cost"] -= avg * q
    holdings = {c: {"qty": h["qty"], "avg_cost": round(h["cost"] / h["qty"], 2), "cost": round(h["cost"], 2)} for c, h in pos.items() if h["qty"] > 0}
    return {"cash": cash, "holdings": holdings, "realized": realized}
