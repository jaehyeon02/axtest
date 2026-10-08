"""전문가 투자의견 계산. 점수와 라벨 규칙을 한곳에 모아 둡니다."""
from .models import Consensus, Stock


def score_of(c: Consensus) -> float:
    """5점 척도 평균(적극매수=5 … 적극매도=1)을 0~100점으로 바꿔요."""
    total = c.strong_buy + c.buy + c.hold + c.sell + c.strong_sell
    if total == 0:
        return 50.0
    avg = (5 * c.strong_buy + 4 * c.buy + 3 * c.hold + 2 * c.sell + c.strong_sell) / total
    return round((avg - 1) / 4 * 100, 1)


def label_of(score: float) -> str:
    if score >= 80:
        return "적극매수"
    if score >= 60:
        return "매수"
    if score >= 40:
        return "중립"
    if score >= 20:
        return "매도"
    return "적극매도"


def to_opinion(stock: Stock, c: Consensus) -> dict:
    total = c.strong_buy + c.buy + c.hold + c.sell + c.strong_sell
    score = score_of(c)
    return {
        "code": stock.code, "price": stock.price,
        "strong_buy": c.strong_buy, "buy": c.buy, "hold": c.hold,
        "sell": c.sell, "strong_sell": c.strong_sell, "total": total,
        "score": score, "label": label_of(score),
        "buy_pct": round((c.strong_buy + c.buy) / total * 100, 1) if total else 0.0,
        "target_avg": c.target_avg, "target_high": c.target_high, "target_low": c.target_low,
        "upside_pct": round((c.target_avg / stock.price - 1) * 100, 1),
        "updated": c.updated,
    }
