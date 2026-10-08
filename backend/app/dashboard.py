"""종목 대시보드(초보자용) 계산.

가격 위치, 기간별 수익률, 신호등, 100만원 시뮬레이션처럼
"숫자를 쉬운 말로 바꿔 주는" 값을 SQL에서 가져온 일봉으로 계산합니다.
LLM 없이 규칙만 쓰기 때문에 같은 데이터면 항상 같은 결과가 나와요.
"""
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .analysis import collect_facts
from .models import Candle, Consensus, Investor, Stock
from .opinion import label_of, score_of

# (표시 이름, 거래일 수)
PERIODS = [("1주", 5), ("1개월", 21), ("3개월", 63), ("6개월", 126), ("1년", 252)]
INVEST = 1_000_000  # 시뮬레이션에 쓰는 투자금(원)


def _candles(db: Session, code: str, n: int = 253):
    rows = db.query(Candle).filter(Candle.code == code).order_by(desc(Candle.day)).limit(n).all()
    rows.reverse()  # 오래된 날 → 오늘
    return rows


def _ret(closes, days: int):
    """days 거래일 전 종가 대비 수익률(%). 데이터가 모자라면 None."""
    if len(closes) <= days or not closes[-1 - days]:
        return None
    return round((closes[-1] / closes[-1 - days] - 1) * 100, 2)


def _range52(rows):
    last = rows[-252:]
    hi = max(r.high for r in last)
    lo = min(r.low for r in last)
    return lo, hi


def quick_insight(db: Session, code: str):
    """홈 카드에 쓰는 요약: 1년 가격 위치, 기간별 수익률, 전문가 의견 라벨."""
    rows = _candles(db, code)
    if not rows:
        return None
    closes = [r.close for r in rows]
    lo, hi = _range52(rows)
    pos = (closes[-1] - lo) / (hi - lo) * 100 if hi > lo else 50.0
    c = db.get(Consensus, code)
    score = score_of(c) if c else None
    total = (c.strong_buy + c.buy + c.hold + c.sell + c.strong_sell) if c else 0
    return {
        "pos52": round(pos, 1), "low52": lo, "high52": hi,
        "ret_1w": _ret(closes, 5), "ret_1m": _ret(closes, 21), "ret_3m": _ret(closes, 63),
        "op_label": label_of(score) if score is not None else None,
        "op_total": total,
    }


def build_dashboard(db: Session, stock: Stock) -> dict:
    rows = _candles(db, stock.code)
    closes = [r.close for r in rows]
    facts = collect_facts(db, stock)
    lo, hi = _range52(rows)
    pos = (stock.price - lo) / (hi - lo) * 100 if hi > lo else 50.0

    periods = [{"label": name, "pct": _ret(closes, d)} for name, d in PERIODS]
    year = next((p["pct"] for p in periods if p["label"] == "1년"), None)
    month = next((p["pct"] for p in periods if p["label"] == "1개월"), None)

    # 최근 5거래일 투자자별 순매수 합계(주)
    inv = db.query(Investor).filter(Investor.code == stock.code).order_by(desc(Investor.day)).limit(5).all()
    net5 = {
        "individual": sum(r.individual for r in inv),
        "foreign": sum(r.foreign for r in inv),
        "institution": sum(r.institution for r in inv),
    }

    c = db.get(Consensus, stock.code)
    score = score_of(c) if c else None
    op_label = label_of(score) if score is not None else None
    op_total = (c.strong_buy + c.buy + c.hold + c.sell + c.strong_sell) if c else 0
    op_buy_pct = ((c.strong_buy + c.buy) / op_total * 100) if c and op_total else 0

    # ── 신호등: good(긍정) / neutral(보통) / bad(주의) ──
    signals = []
    if facts["ma5"] > facts["ma20"] > facts["ma60"]:
        signals.append(("flow", "가격 흐름", "good", "최근 평균 가격이 단계적으로 올라가는 흐름이에요."))
    elif facts["ma5"] < facts["ma20"] < facts["ma60"]:
        signals.append(("flow", "가격 흐름", "bad", "최근 평균 가격이 단계적으로 내려가는 흐름이에요."))
    else:
        signals.append(("flow", "가격 흐름", "neutral", "오르내림이 섞여 있어 방향이 뚜렷하지 않아요."))

    vr = facts["volume_ratio"]
    if vr >= 1.5:
        signals.append(("heat", "거래 열기", "good", f"평소보다 {vr:.1f}배 거래돼요. 관심이 몰리고 있어요."))
    elif vr <= 0.7:
        signals.append(("heat", "거래 열기", "bad", f"평소의 {vr:.1f}배로 거래가 한산해요."))
    else:
        signals.append(("heat", "거래 열기", "neutral", "평소와 비슷한 수준으로 거래돼요."))

    smart = net5["foreign"] + net5["institution"]
    thr = max(1, int(stock.volume * 0.03))
    if smart > thr:
        signals.append(("supply", "큰손 움직임", "good", "최근 5일 외국인·기관이 사는 쪽이었어요."))
    elif smart < -thr:
        signals.append(("supply", "큰손 움직임", "bad", "최근 5일 외국인·기관이 파는 쪽이었어요."))
    else:
        signals.append(("supply", "큰손 움직임", "neutral", "최근 5일 외국인·기관이 사고판 양이 비슷해요."))

    if op_label in ("적극매수", "매수"):
        signals.append(("expert", "전문가 의견", "good", f"전문가 {op_total}명 중 {op_buy_pct:.0f}%가 매수 의견이에요."))
    elif op_label == "중립":
        signals.append(("expert", "전문가 의견", "neutral", f"전문가 {op_total}명의 의견이 중립에 가까워요."))
    elif op_label:
        signals.append(("expert", "전문가 의견", "bad", f"전문가 {op_total}명의 의견이 매도 쪽으로 기울어 있어요."))

    # ── 쉬운 말 요약 ──
    if stock.change_rate > 0.3:
        today = f"오늘 {stock.name} 주가는 {abs(stock.change_rate):.2f}% 올랐어요."
    elif stock.change_rate < -0.3:
        today = f"오늘 {stock.name} 주가는 {abs(stock.change_rate):.2f}% 내렸어요."
    else:
        today = f"오늘 {stock.name} 주가는 거의 변동이 없어요."
    summary = [today]
    zone = "높은" if pos >= 67 else "낮은" if pos < 33 else "중간쯤의"
    month_text = f"최근 1개월은 {month:+.1f}% 움직였고, " if month is not None else ""
    summary.append(f"{month_text}지금 가격은 1년 중 {zone} 위치예요(저점 0 ~ 고점 100 중 {pos:.0f}).")
    if op_label:
        ending = "이에요" if op_label == "중립" else "예요"  # 받침이 있으면 '이에요'
        summary.append(f"전문가 {op_total}명의 종합 의견은 '{op_label}'{ending}.")

    return {
        "code": stock.code,
        "summary": summary,
        "signals": [{"key": k, "title": t, "status": s, "text": x} for k, t, s, x in signals],
        "pos52": round(pos, 1), "low52": lo, "high52": hi,
        "periods": periods,
        "simulation": {
            "invested": INVEST,
            "value": round(INVEST * (1 + year / 100)) if year is not None else INVEST,
            "pct": year if year is not None else 0.0,
        },
        "heat": {"volume_ratio": round(vr, 2), "value_rank": facts["rank"], "buy_ratio": stock.buy_ratio},
        "net5": net5,
    }


def volatility(db, code, days=60):
    """최근 days일 일간 수익률의 표준편차(%). 값이 클수록 가격이 크게 출렁인다는 뜻이에요."""
    closes = [
        r.close
        for r in db.query(Candle).filter(Candle.code == code).order_by(Candle.day.desc()).limit(days + 1).all()
    ][::-1]
    rets = [(b / a - 1) * 100 for a, b in zip(closes, closes[1:]) if a]
    if len(rets) < 2:
        return 0.0
    m = sum(rets) / len(rets)
    return round((sum((x - m) ** 2 for x in rets) / (len(rets) - 1)) ** 0.5, 2)
