"""샘플 데이터 생성.

실제 시세 API를 연결하기 전까지 화면을 채우는 용도의 데이터입니다.
현재가·등락률·거래대금은 스크린샷 값을 기준으로 하고, 과거 일봉은 난수로 만든 예시예요.
나중에 pykrx / yfinance / 공공데이터 API 수집 코드로 이 파일의 내용을 바꾸면 됩니다.
"""
import json
import math
import random
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from .models import Candle, Consensus, Investor, MarketIndex, News, Stock

# (코드, 이름, 시장, 산업, 현재가, 등락률, 거래대금(억), 시가총액(억), 매수비율, 로고글자, 로고색, 변동성)
STOCKS = [
    ("000660", "SK하이닉스", "kr", "종합반도체", 1776000, -3.53, 159, 13448000, 18, "S", "#e4202e", 0.024),
    ("005930", "삼성전자", "kr", "종합반도체", 272500, -1.26, 80, 17753000, 33, "삼", "#1428a0", 0.018),
    ("122630", "KODEX 레버리지", "kr", None, 111800, -2.26, 46, 59000, 61, "2x", "#2d6df6", 0.032),
    ("009150", "삼성전기", "kr", "스마트폰MLCC", 1672000, 5.75, 38, 1193000, 77, "삼", "#1428a0", 0.026),
    ("233740", "KODEX 반도체레버리지", "kr", "반도체", 106855, 2.70, 38, 13000, 62, "2x", "#2d6df6", 0.034),
    ("161890", "한국콜마", "kr", "화장품제조", 138600, 1.46, 24, 32000, 77, "콜", "#1a73c8", 0.022),
    ("036930", "주성엔지니어링", "kr", "반도체 전공정 장비", 278000, 17.29, 21, 111000, 69, "주", "#c8312b", 0.034),
    ("069500", "KODEX 200", "kr", None, 110785, -1.13, 19, 259000, 63, "200", "#2d6df6", 0.016),
    ("006400", "삼성SDI", "kr", "배터리제조", 574000, 8.50, 18, 430000, 77, "삼", "#1428a0", 0.028),
    ("010120", "LS ELECTRIC", "kr", "전기설비", 216500, 3.34, 14, 314000, 84, "LS", "#0a4aa6", 0.026),
    ("402340", "SK스퀘어", "kr", "지주사", 1160000, 0.00, 14, 1526000, 68, "S", "#e4202e", 0.024),
    ("233160", "KODEX 코스닥150레버리지", "kr", None, 8700, 8.27, 13, 4000, 64, "2x", "#2d6df6", 0.04),
    ("066570", "LG전자", "kr", "컴퓨터와 주변기기", 231750, 7.29, 13, 364000, 72, "L", "#c31f3d", 0.024),
    ("033240", "엠케이전자", "kr", "반도체 부품", 19500, -2.25, 9, 3200, 40, "M", "#d6342a", 0.032),
    ("247540", "에코프로비엠", "kr", "2차전지 소재", 128700, 11.23, 8, 125000, 63, "E", "#1457c4", 0.034),
    ("007660", "빛과전자", "kr", "광통신 부품", 5010, 13.86, 6, 1700, 58, "빛", "#d63a2f", 0.04),
    ("003670", "포스코퓨처엠", "kr", "2차전지 소재", 204500, 9.41, 6, 158000, 67, "P", "#2b4a8b", 0.03),
    ("253590", "네오셈", "kr", "반도체 검사장비", 16230, 4.17, 4, 2300, 55, "N", "#d8123b", 0.036),
    ("007810", "아비코전자", "kr", "전자부품", 8340, 0.00, 3, 2500, 50, "A", "#4a90d9", 0.028),
    ("SOXL", "SOXL", "us", "반도체", 224750, 0.71, 20, 362000, 34, "3x", "#f5a524", 0.045),
    ("WSSH", "와이즈셋 스페이스 홀딩스", "us", None, 9726, 7.34, 18, 2931, 49, "와", "#8a93a6", 0.05),
    ("SOXS", "SOXS", "us", "반도체", 39980, -0.64, 12, 22000, 75, "3x", "#f5a524", 0.045),
    ("QTRX", "큐트렉스 퀀텀", "us", "양자컴퓨터", 2458, 17.53, 12, 14040, 51, "큐", "#5f6b8a", 0.06),
    ("KORU", "KORU", "us", None, 29520, -4.60, 9.4, 21000, 47, "3x", "#2f6fe4", 0.05),
    ("TQQQ", "TQQQ", "us", None, 113516, 0.52, 7.9, 547000, 88, "3x", "#1c9c5a", 0.035),
    ("SPCX", "스페이스X", "us", "우주항공", 234911, 1.06, 7.4, 31572000, 49, "SX", "#111111", 0.03),
    ("NVDA", "엔비디아", "us", "반도체팹리스", 326094, 0.47, 3.5, 78279000, 92, "N", "#4f8f00", 0.025),
    ("USDD", "스테이블코인 디벨롭먼트", "us", "암호화폐", 4184, -21.82, 3.4, 27720, 38, "S", "#2e6ff2", 0.06),
    ("MU", "마이크론 테크놀로지", "us", "종합반도체", 1436369, -0.62, 2.6, 16337000, 50, "M", "#6a7280", 0.03),
    ("IREN", "아이렌", "us", "암호화폐", 55209, 0.39, 2.3, 217000, 5, "I", "#3ab26a", 0.05),
    ("TSLA", "테슬라", "us", "전기차", 517411, 0.56, 2.2, 20337000, 35, "T", "#e0232a", 0.03),
    ("SNDK", "샌디스크", "us", "종합반도체", 2306773, -0.35, 2.0, 3392000, 23, "S", "#e8453c", 0.035),
]

INDICES = [
    ("코스피", 6933.61, -70.13, -1.00, 0.010),
    ("코스닥", 917.46, 24.17, 2.70, 0.012),
    ("달러 환율", 1343.35, -15.15, -1.11, 0.004),
    ("나스닥", 27477.31, 286.45, 1.05, 0.010),
    ("S&P 500", 7773.95, 51.23, 0.66, 0.008),
    ("필라델피아 반도체", 13172.73, 36.06, 0.27, 0.014),
    ("VIX", 15.52, 0.21, 1.37, 0.05),
]

NEWS_POS = [
    "{name}, 업황 회복 기대감에 투자심리 개선",
    "{name} 목표주가 줄줄이 상향…\"{sector} 수요 견조\"",
    "외국인·기관 동반 순매수에 {name} 강세",
    "{sector} 업종 강세 속 {name} 거래대금 급증",
]
NEWS_NEG = [
    "{name}, 차익실현 매물 출회로 단기 조정",
    "금리 부담에 {sector} 투자심리 위축…{name} 약세",
    "{name} 외국인 순매도 확대, 거래대금은 증가",
    "{sector} 업종 전반 하락, {name}도 동반 약세",
]
NEWS_NEU = [
    "{name}, 관망세 속 보합권 등락",
    "{name} 다음 주 주요 일정 앞두고 거래 한산",
]
SOURCES = ["연합뉴스", "한국경제", "매일경제", "머니투데이", "서울경제"]


def _trading_days(end: date, n: int):
    days, d = [], end
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def _make_candles(code: str, price: float, prev_close: float, base_volume: int, vol: float, n: int = 520):
    """오늘 종가(price)와 어제 종가(prev_close)를 맞춘 뒤, 과거로 거슬러 올라가며 난수 일봉을 만듭니다."""
    rnd = random.Random(code)
    closes = [price, prev_close]
    while len(closes) < n:
        closes.append(closes[-1] / (1 + rnd.gauss(0.0004, vol)))
    closes.reverse()  # 오래된 날 → 오늘

    days = _trading_days(date(2026, 10, 6), n)
    rows = []
    for i, (day, c) in enumerate(zip(days, closes)):
        o = closes[i - 1] if i else c * (1 + rnd.gauss(0, vol * 0.3))
        hi = max(o, c) * (1 + abs(rnd.gauss(0, vol * 0.5)))
        lo = min(o, c) * (1 - abs(rnd.gauss(0, vol * 0.5)))
        swing = abs(c - o) / o if o else 0
        v = int(base_volume * (0.5 + rnd.random()) * (1 + swing * 15))
        if i == n - 1:
            v = base_volume
        rows.append((day, round(o), round(hi), round(lo), round(c), v))
    return rows


def _sparkline(name: str, end_value: float, rate: float, vol: float, n: int = 40):
    rnd = random.Random(name)
    start = end_value / (1 + rate / 100)
    vals = [start]
    for _ in range(n - 2):
        vals.append(vals[-1] * (1 + rnd.gauss(0, vol * 0.4)))
    vals.append(end_value)
    return [round(v, 2) for v in vals]


def _round_sig(x: float, digits: int = 3) -> float:
    """목표주가를 '1,780,000'처럼 앞 3자리만 남겨 둥글게 만듭니다."""
    if x <= 0:
        return 0
    scale = 10 ** max(0, int(math.floor(math.log10(x))) - digits + 1)
    return round(x / scale) * scale


def _make_consensus(code: str, price: float, rate: float, buy_ratio: int):
    """전문가 의견 수와 목표주가 샘플. 등락률과 매수비율이 높을수록 매수 쪽으로 기울어요."""
    rnd = random.Random(code + "consensus")
    tilt = max(-1.0, min(1.0, (buy_ratio - 50) / 50 * 0.6 + rate / 25))
    mean = max(1.2, min(4.8, 3.2 + 1.3 * tilt + rnd.gauss(0, 0.25)))
    n = rnd.randint(8, 30)
    weights = [math.exp(-((k - mean) ** 2) / (2 * 0.85**2)) for k in (5, 4, 3, 2, 1)]
    total_w = sum(weights)
    counts = [int(n * w / total_w) for w in weights]
    counts[counts.index(max(counts))] += n - sum(counts)  # 반올림 오차는 가장 큰 칸에 더해요
    avg = price * (1 + 0.06 + 0.14 * tilt + rnd.gauss(0, 0.02))
    high = avg * (1.10 + rnd.random() * 0.15)
    low = avg * (0.82 + rnd.random() * 0.10)
    return counts, _round_sig(avg), _round_sig(high), _round_sig(low)


def seed_consensus(db: Session):
    """consensus 테이블이 비어 있으면 채웁니다. (예전 버전 DB를 쓰는 경우에도 동작)"""
    if db.query(Consensus).count():
        return
    for st in db.query(Stock).all():
        (sb, b, h, s, ss), avg, high, low = _make_consensus(st.code, st.price, st.change_rate, st.buy_ratio)
        db.add(Consensus(
            code=st.code, strong_buy=sb, buy=b, hold=h, sell=s, strong_sell=ss,
            target_avg=avg, target_high=high, target_low=low, updated=date(2026, 10, 6),
        ))
    db.commit()


def seed(db: Session):
    if db.query(Stock).count():
        seed_consensus(db)
        return

    today = datetime(2026, 10, 6, 15, 20)
    for (code, name, market, sector, price, rate, tv, cap, buy, ltxt, lcol, vol) in STOCKS:
        prev = round(price / (1 + rate / 100))
        base_volume = max(1, int(tv * 1e8 / price))
        rows = _make_candles(code, price, prev, base_volume, vol)
        db.add(Stock(
            code=code, name=name, market=market, sector=sector, price=price, prev_close=prev,
            change_rate=rate, trade_value=tv, volume=base_volume, market_cap=cap, buy_ratio=buy,
            logo_text=ltxt, logo_color=lcol,
        ))
        db.flush()
        db.bulk_save_objects([
            Candle(code=code, day=d, open=o, high=h, low=l, close=c, volume=v) for (d, o, h, l, c, v) in rows
        ])

        rnd = random.Random(code + "news")
        pool = NEWS_POS if rate > 0.3 else NEWS_NEG if rate < -0.3 else NEWS_NEU
        sentiment = "pos" if rate > 0.3 else "neg" if rate < -0.3 else "neu"
        for k, tpl in enumerate(rnd.sample(pool, min(3, len(pool)))):
            db.add(News(
                code=code, sentiment=sentiment, source=rnd.choice(SOURCES),
                title=tpl.format(name=name, sector=sector or "관련"),
                published_at=today - timedelta(minutes=rnd.randint(5, 60) + k * 90),
            ))

        # 최근 5거래일 투자자별 순매수(주). 개인은 외국인+기관의 반대 방향으로 만듭니다.
        for d in _trading_days(date(2026, 10, 6), 5):
            f = int(rnd.gauss(0, base_volume * 0.08))
            ins = int(rnd.gauss(0, base_volume * 0.06))
            db.add(Investor(code=code, day=d, individual=-(f + ins), foreign=f, institution=ins))

    for order, (name, value, change, rate, vol) in enumerate(INDICES):
        db.add(MarketIndex(
            name=name, sort_order=order, value=value, change=change, change_rate=rate,
            series=json.dumps(_sparkline(name, value, rate, vol)),
        ))
    db.commit()
    seed_consensus(db)
