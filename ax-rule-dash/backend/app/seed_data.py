"""개발용 가상 샘플 데이터 생성기 (순수 파이썬). 인터넷·API 키 없이 화면과 백테스트를 확인하려는 용도예요.
여기 시세는 전부 난수로 만든 가짜이고 실제 수치가 아니에요. 실제 시세는 `python -m app.ingest` 가 pykrx 에서 받아요."""
import math
import random
from datetime import date, timedelta

END = date(2026, 10, 7)  # 마지막 거래일
DAYS = 500  # 약 2년치

SECTORS = ["반도체", "인터넷", "자동차", "2차전지", "바이오"]
# code, name, market, sector, 기준가, 하루 변동폭, 연매출(억원), 영업이익률, 기준 PER, 기준 PBR
COMPANIES = [
    ("005930", "삼성전자", "KOSPI", "반도체", 72000, 0.014, 3000000, 0.1, 14.0, 1.2),
    ("000660", "SK하이닉스", "KOSPI", "반도체", 190000, 0.022, 660000, 0.28, 9.0, 1.9),
    ("035420", "NAVER", "KOSPI", "인터넷", 210000, 0.019, 100000, 0.17, 22.0, 1.6),
    ("035720", "카카오", "KOSPI", "인터넷", 48000, 0.024, 80000, 0.07, 45.0, 1.8),
    ("005380", "현대차", "KOSPI", "자동차", 245000, 0.016, 1700000, 0.08, 5.5, 0.6),
    ("000270", "기아", "KOSPI", "자동차", 105000, 0.017, 1000000, 0.11, 5.0, 0.8),
    ("373220", "LG에너지솔루션", "KOSPI", "2차전지", 380000, 0.026, 250000, 0.05, 70.0, 4.5),
    ("068270", "셀트리온", "KOSPI", "바이오", 180000, 0.021, 35000, 0.3, 35.0, 3.2),
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
    companies, prices, funds, fins, price_id = [], [], [], [], 0
    for cid, (code, name, market, sector, base, sigma, rev0, margin, per0, pbr0) in enumerate(COMPANIES, start=1):
        companies.append({"company_id": cid, "code": code, "name": name, "market": market, "sector_id": sid[sector], "corp_code": None})
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
            eps, bps = base / per0, base / pbr0  # 샘플: EPS·BPS 는 일정하다고 보고 PER·PBR 이 주가를 따라 움직이게 해요
            funds.append({"fund_id": price_id, "company_id": cid, "trade_date": d, "per": round(c / eps, 2), "pbr": round(c / bps, 2), "eps": round(eps, 2), "bps": round(bps, 2)})
            close = c
        growth, rev = rng.uniform(-0.02, 0.09), rev0 * rng.uniform(0.75, 0.9)
        for fy in range(2021, 2026):  # 연간 재무 5개년
            rev *= 1 + growth + rng.gauss(0, 0.04)
            op = rev * (margin + rng.gauss(0, 0.025))
            fins.append({"fin_id": cid * 10 + fy - 2020, "company_id": cid, "fiscal_year": fy, "revenue": round(rev, 1), "operating_profit": round(op, 1), "net_income": round(op * rng.uniform(0.6, 0.85), 1)})
    return {"sector": sectors, "company": companies, "price_daily": prices, "fundamental_daily": funds, "financial_year": fins}
