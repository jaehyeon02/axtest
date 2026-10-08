"""종목 분석(왜 올랐을까 / 왜 떨어졌을까).

지금은 DB의 수치(이동평균, 거래량, 52주 위치, 매수비율)와 뉴스 제목을 규칙으로 묶어서 설명해요.
mode="rule" 이 그 뜻이에요.

나중에 RAG를 붙일 때는 build_analysis() 안의 `reasons` 를 만드는 부분만 바꾸면 됩니다.
  1) 뉴스·공시 본문을 Vector DB(Chroma 등)에 저장
  2) 아래에서 계산한 수치(facts)와 검색된 문서를 LLM 프롬프트로 전달
  3) LLM이 쓴 문장을 reasons 로 반환, mode="llm" 으로 표시
LLM에게 판단을 맡기지 말고, 계산한 수치를 설명하게 하는 구조를 권장합니다.
"""
from statistics import mean

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from .models import Candle, News, Stock


def _direction(rate: float) -> str:
    return "up" if rate > 0.3 else "down" if rate < -0.3 else "flat"


def collect_facts(db: Session, stock: Stock) -> dict:
    """분석에 쓰는 정량 지표를 SQL로 계산합니다."""
    rows = (
        db.query(Candle).filter(Candle.code == stock.code)
        .order_by(desc(Candle.day)).limit(260).all()
    )
    rows.reverse()
    closes = [r.close for r in rows]
    vols = [r.volume for r in rows]

    ma5, ma20, ma60 = (mean(closes[-n:]) for n in (5, 20, 60))
    avg_vol20 = mean(vols[-21:-1]) if len(vols) > 21 else mean(vols)
    hi, lo = max(r.high for r in rows), min(r.low for r in rows)
    pos52 = (stock.price - lo) / (hi - lo) * 100 if hi > lo else 50

    rank = (
        db.query(func.count(Stock.code))
        .filter(Stock.market == stock.market, Stock.trade_value > stock.trade_value).scalar() + 1
    )
    return {
        "ma5": ma5, "ma20": ma20, "ma60": ma60,
        "volume_ratio": stock.volume / avg_vol20 if avg_vol20 else 1,
        "pos52": pos52, "week52_high": hi, "week52_low": lo, "rank": rank,
    }


def build_analysis(db: Session, stock: Stock) -> dict:
    f = collect_facts(db, stock)
    d = _direction(stock.change_rate)
    verb = {"up": "상승", "down": "하락", "flat": "보합"}[d]
    question = {"up": "왜 올랐을까?", "down": "왜 떨어졌을까?", "flat": "오늘은 어떤가요?"}[d]
    market_label = "국내" if stock.market == "kr" else "해외"

    headline = f"{stock.name} {stock.change_rate:+.2f}% {verb}, {market_label} 거래대금 {f['rank']}위"

    reasons = []
    vr = f["volume_ratio"]
    if vr >= 1.5:
        reasons.append(f"거래량이 최근 20일 평균의 {vr:.1f}배로 크게 늘었어요.")
    elif vr <= 0.7:
        reasons.append(f"거래량이 최근 20일 평균의 {vr:.1f}배로 한산했어요.")
    else:
        reasons.append(f"거래량은 최근 20일 평균과 비슷한 수준이에요({vr:.1f}배).")

    if f["ma5"] > f["ma20"] > f["ma60"]:
        reasons.append("5일·20일·60일 이동평균선이 위에서부터 차례로 놓인 정배열 흐름이에요.")
    elif f["ma5"] < f["ma20"] < f["ma60"]:
        reasons.append("5일·20일·60일 이동평균선이 아래에서부터 차례로 놓인 역배열 흐름이에요.")
    else:
        side = "위" if stock.price >= f["ma20"] else "아래"
        reasons.append(f"현재가가 20일 이동평균선({f['ma20']:,.0f}원) {side}에 있어요.")

    reasons.append(
        f"52주 범위({f['week52_low']:,.0f}원~{f['week52_high']:,.0f}원)에서 "
        f"{f['pos52']:.0f}% 위치예요."
    )
    if stock.buy_ratio >= 55:
        tilt = "매수세가 우위예요."
    elif stock.buy_ratio <= 45:
        tilt = "매도세가 우위예요."
    else:
        tilt = "매수·매도가 비슷해요."
    reasons.append(f"매수 체결 비율 {stock.buy_ratio}% · 매도 {100 - stock.buy_ratio}%로 {tilt}")

    news = (
        db.query(News).filter(News.code == stock.code)
        .order_by(desc(News.published_at)).limit(3).all()
    )
    return {
        "code": stock.code, "direction": d, "question": question, "headline": headline,
        "reasons": reasons, "mode": "rule", "news": news,
    }
