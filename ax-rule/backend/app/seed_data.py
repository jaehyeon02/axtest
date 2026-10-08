"""개발용 가상 샘플 데이터 생성기 (순수 파이썬). 인터넷·API 키 없이 화면과 백테스트를 확인하려는 용도예요.
여기 시세는 전부 난수로 만든 가짜이고 실제 수치가 아니에요. 실제 시세는 `python -m app.ingest` 가 pykrx 에서 받아요."""
import math
import random
from datetime import date, timedelta

END = date(2026, 10, 7)  # 마지막 거래일
DAYS = 500  # 약 2년치

SECTORS = ["반도체", "인터넷", "자동차", "2차전지", "바이오"]
# code, name, market, sector, 기준가, 하루 변동폭
COMPANIES = [
    ("005930", "삼성전자", "KOSPI", "반도체", 72000, 0.014),
    ("000660", "SK하이닉스", "KOSPI", "반도체", 190000, 0.022),
    ("035420", "NAVER", "KOSPI", "인터넷", 210000, 0.019),
    ("035720", "카카오", "KOSPI", "인터넷", 48000, 0.024),
    ("005380", "현대차", "KOSPI", "자동차", 245000, 0.016),
    ("000270", "기아", "KOSPI", "자동차", 105000, 0.017),
    ("373220", "LG에너지솔루션", "KOSPI", "2차전지", 380000, 0.026),
    ("068270", "셀트리온", "KOSPI", "바이오", 180000, 0.021),
]


def trading_days(end: date, n: int):
    days, d = [], end
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return days[::-1]


def _round_price(x: float) -> int:
    step = 1000 if x >= 500000 else 500 if x >= 200000 else 100 if x >= 50000 else 50 if x >= 20000 else 10
    return int(round(x / step) * step)


def generate():
    days = trading_days(END, DAYS)
    sectors = [{"sector_id": i + 1, "name": n} for i, n in enumerate(SECTORS)]
    sid = {s["name"]: s["sector_id"] for s in sectors}
    companies, prices, price_id = [], [], 0
    for cid, (code, name, market, sector, base, sigma) in enumerate(COMPANIES, start=1):
        companies.append({"company_id": cid, "code": code, "name": name, "market": market, "sector_id": sid[sector]})
        rng = random.Random(int(code))
        phase, period = rng.uniform(0, 6.28), rng.uniform(70, 130)  # 오르고 내리는 큰 물결(추세 구간)을 만들어 돌파·이동평균 규칙이 작동하게
        signs = [1, -1] * 6  # 급등·급락을 같은 수로 섞어 장기 쏠림을 막아요
        rng.shuffle(signs)
        spikes = {rng.randrange(20, DAYS - 3): sg * rng.uniform(4.5, 9) for sg in signs}
        close = float(base)
        for i, d in enumerate(days):
            prev = close
            drift = 0.0012 * math.sin(i / period * 6.28 + phase)
            ret = max(-0.035, min(0.035, math.exp(rng.gauss(drift - sigma * sigma / 2, sigma)) - 1))  # 로그수익률 기준으로 뽑아 장기 쏠림을 줄여요
            if i in spikes:
                ret = spikes[i] / 100 + rng.gauss(0, sigma / 4)
            close = max(prev * (1 + ret), base * 0.25)
            o = _round_price(prev * (1 + rng.gauss(0, sigma / 3)))
            c = _round_price(close)
            hi = max(_round_price(max(o, c) * (1 + abs(rng.gauss(0, sigma / 2)))), o, c)
            lo = min(_round_price(min(o, c) * (1 - abs(rng.gauss(0, sigma / 2)))), o, c)
            vol = int(rng.uniform(0.8, 1.2) * 2_000_000 * (2.5 if i in spikes else rng.uniform(0.6, 1.4)) * (100000 / max(base, 20000)) ** 0.5)
            price_id += 1
            prices.append({"price_id": price_id, "company_id": cid, "trade_date": d, "open": o, "high": hi, "low": lo, "close": c, "volume": vol})
            close = c
    return {"sector": sectors, "company": companies, "price_daily": prices}
