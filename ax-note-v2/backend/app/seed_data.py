"""샘플 데이터 생성기 (순수 파이썬: DB·프레임워크 없이도 실행돼요).

인터넷이 없거나 API 키가 없을 때 화면을 확인하려는 용도예요. 실제 데이터는 `python -m app.ingest` 가 pykrx·OpenDART 에서 받아 같은 테이블에 넣어요.
여기 시세·재무·공시는 전부 개발용 가상 데이터이고, 실제 수치가 아니에요.
"""
import random
from datetime import date, timedelta

END = date(2026, 10, 7)  # 마지막 거래일
DAYS = 250  # 거래일 수

SECTORS = ["반도체", "인터넷", "자동차", "2차전지", "바이오"]

# code, name, market, sector, 기준가, 하루 변동폭, 연매출(억원), 영업이익률
COMPANIES = [
    ("005930", "삼성전자", "KOSPI", "반도체", 72000, 0.014, 3000000, 0.10),
    ("000660", "SK하이닉스", "KOSPI", "반도체", 190000, 0.022, 660000, 0.28),
    ("035420", "NAVER", "KOSPI", "인터넷", 210000, 0.019, 100000, 0.17),
    ("035720", "카카오", "KOSPI", "인터넷", 48000, 0.024, 80000, 0.07),
    ("005380", "현대차", "KOSPI", "자동차", 245000, 0.016, 1700000, 0.08),
    ("000270", "기아", "KOSPI", "자동차", 105000, 0.017, 1000000, 0.11),
    ("373220", "LG에너지솔루션", "KOSPI", "2차전지", 380000, 0.026, 250000, 0.05),
    ("068270", "셀트리온", "KOSPI", "바이오", 180000, 0.021, 35000, 0.30),
]

# 호재(topic, effect) / 악재(topic, effect): 업종별
TOPICS = {
    "반도체": {
        "pos": [("HBM 공급 확대 기대", "메모리 가격 반등과 가동률 상승이 실적에 긍정적일 것"),
                ("AI 서버용 반도체 수요 증가", "수주 잔고가 늘며 하반기 실적 개선 가능성이 크다"),
                ("파운드리 신규 고객 확보", "공정 수율 개선이 수익성으로 이어질 것")],
        "neg": [("메모리 재고 부담", "재고 조정이 길어지면 가격 하락 압력이 커질 수 있다"),
                ("수출 규제 확대", "중국 매출 비중이 높아 단기 변동성이 커질 수 있다"),
                ("설비투자 지연", "신규 라인 가동 시점이 늦어질 수 있다")],
    },
    "인터넷": {
        "pos": [("광고 매출 호조", "온라인 광고 단가 상승이 영업이익을 끌어올릴 것"),
                ("AI 검색·서비스 출시", "이용자 체류시간이 늘어 수익화 기대가 커졌다"),
                ("커머스 거래액 성장", "거래액 증가가 수수료 수익으로 이어질 것")],
        "neg": [("플랫폼 규제 강화", "수수료 규제로 수익성이 낮아질 수 있다"),
                ("서비스 장애", "신뢰도 하락과 보상 비용 우려가 있다"),
                ("콘텐츠 투자 부담", "비용 증가로 이익 개선이 늦어질 수 있다")],
    },
    "자동차": {
        "pos": [("북미 판매 증가", "차종 구성 개선으로 영업이익률이 높아질 것"),
                ("신형 전기차 출시", "판매량 확대와 브랜드 경쟁력 강화가 기대된다"),
                ("환율 효과", "원화 약세가 수출 채산성을 높일 것")],
        "neg": [("관세 부담", "관세 비용이 수익성을 압박할 수 있다"),
                ("리콜 발생", "리콜 비용과 이미지 훼손이 부담이다"),
                ("전기차 수요 둔화", "재고 증가와 판촉비 확대가 우려된다")],
    },
    "2차전지": {
        "pos": [("북미 공장 가동률 상승", "고정비 부담이 줄어 수익성이 좋아질 것"),
                ("대형 배터리 공급 계약", "중장기 매출 가시성이 높아졌다"),
                ("보조금 확대", "전기차 수요 회복이 기대된다")],
        "neg": [("전기차 수요 둔화", "주문이 줄어 가동률이 낮아질 수 있다"),
                ("원자재 가격 급변", "원가 부담이 커질 수 있다"),
                ("화재 이슈", "안전성 논란이 커질 수 있다")],
    },
    "바이오": {
        "pos": [("임상 3상 긍정 결과", "허가 가능성이 높아져 기업가치가 재평가될 것"),
                ("해외 판매 확대", "신규 시장 진출이 매출을 키울 것"),
                ("기술수출 계약", "계약금 유입이 기대된다")],
        "neg": [("임상 지연", "상업화 시점이 늦어질 수 있다"),
                ("약가 인하 우려", "가격 인하가 수익성을 낮출 수 있다"),
                ("경쟁 제품 출시", "점유율 하락 우려가 있다")],
    },
}

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


def _event_days(rng: random.Random, n: int):
    """급등락일 인덱스: 간격 8일 이상, 최근 45거래일 안에 2개는 꼭 포함."""
    picks = []
    recent = rng.sample(range(n - 45, n - 2), 2)
    while abs(recent[0] - recent[1]) < 8:
        recent = rng.sample(range(n - 45, n - 2), 2)
    picks += recent
    tries = 0
    while len(picks) < 8 and tries < 500:
        tries += 1
        i = rng.randrange(15, n - 46)
        if all(abs(i - p) >= 8 for p in picks):
            picks.append(i)
    return sorted(picks)


def generate():
    """모든 테이블에 넣을 행을 딕셔너리로 돌려줘요. (id는 1부터 순서대로)"""
    days = trading_days(END, DAYS)
    sectors = [{"sector_id": i + 1, "name": n} for i, n in enumerate(SECTORS)]
    sector_id = {s["name"]: s["sector_id"] for s in sectors}

    companies, prices, fins, docs = [], [], [], []
    price_id = doc_id = fin_id = 0

    for cid, (code, name, market, sector, base, sigma, rev0, margin) in enumerate(COMPANIES, start=1):
        companies.append({"company_id": cid, "code": code, "name": name, "market": market, "sector_id": sector_id[sector], "corp_code": None})
        rng = random.Random(int(code))

        events = {i: (rng.choice([1, -1]), rng.uniform(4.5, 9.5)) for i in _event_days(rng, DAYS)}
        close = float(base)
        for i, d in enumerate(days):
            prev = close
            if i in events:
                sign, mag = events[i]
                ret = sign * mag / 100 + rng.gauss(0, sigma / 4)
            else:
                ret = rng.gauss(0.0002, sigma)
                ret = max(-0.035, min(0.035, ret))  # 평범한 날은 ±3.5% 안에서만
            close = max(prev * (1 + ret), base * 0.2)
            o = _round_price(prev * (1 + rng.gauss(0, sigma / 3)))
            c = _round_price(close)
            hi = _round_price(max(o, c) * (1 + abs(rng.gauss(0, sigma / 2))))
            lo = _round_price(min(o, c) * (1 - abs(rng.gauss(0, sigma / 2))))
            hi, lo = max(hi, o, c), min(lo, o, c)
            vol_mult = rng.uniform(2.0, 3.5) if i in events else rng.uniform(0.6, 1.4)
            volume = int(rng.uniform(0.8, 1.2) * 2_000_000 * vol_mult * (100000 / max(base, 20000)) ** 0.5)
            price_id += 1
            prices.append({"price_id": price_id, "company_id": cid, "trade_date": d, "open": o, "high": hi, "low": lo, "close": c, "volume": volume})
            close = c

        # 연간 재무: 2021 ~ 2025 (5개년)
        growth = rng.uniform(-0.02, 0.09)
        rev = rev0 * rng.uniform(0.75, 0.9)
        for fy in range(2021, 2026):
            rev *= 1 + growth + rng.gauss(0, 0.04)
            op = rev * (margin + rng.gauss(0, 0.025))
            fin_id += 1
            fins.append({"fin_id": fin_id, "company_id": cid, "fiscal_year": fy, "revenue": round(rev, 1),
                         "operating_profit": round(op, 1), "net_income": round(op * rng.uniform(0.6, 0.85), 1)})

        def add_filing(title, body, published):
            nonlocal doc_id
            doc_id += 1
            docs.append({"doc_id": doc_id, "company_id": cid, "doc_type": "filing", "title": title, "body": body,
                         "source": "전자공시시스템(샘플)", "sentiment": "neu", "published_date": published,
                         "rcept_no": f"SAMPLE-{code}-{doc_id}", "url": None, "created_by": None})

        # 급등락일마다 관련 공시 1건(당일 또는 전날)
        for i, (sign, _) in events.items():
            pol = "pos" if sign > 0 else "neg"
            topic, effect = rng.choice(TOPICS[sector][pol])
            when = days[i] if rng.random() < 0.6 else days[i - 1]
            if pol == "pos":
                add_filing(f"단일판매·공급계약체결({topic})", f"{name}은(는) {topic}과 관련한 계약을 체결했다고 공시했다. 계약 규모는 최근 매출액의 일부에 해당한다.", when)
            else:
                add_filing(f"주요사항보고서({topic})", f"{name}은(는) {topic}과 관련한 사항을 공시했다. 회사는 영향을 점검 중이라고 밝혔다.", when)

        # 정기 공시: 분기보고서(5·8·11월 중순), 사업보고서(3월 말)
        for y, m, label in ((2025, 11, "분기보고서 (2025.09)"), (2026, 3, "사업보고서 (2025.12)"), (2026, 5, "분기보고서 (2026.03)"), (2026, 8, "반기보고서 (2026.06)")):
            when = date(y, m, 14 if m != 3 else 28)
            if days[0] <= when <= END:
                add_filing(label, f"{name}의 정기 보고서가 제출됐다.", when)
        # 평범한 공시 몇 건
        for t in rng.sample(days[10:], 3):
            title = rng.choice(["임원ㆍ주요주주특정증권등소유상황보고서", "주주총회소집결의", "자기주식취득결과보고서"])
            add_filing(title, f"{name}이(가) {title}를 제출했다.", t)

    docs.sort(key=lambda d: (d["published_date"], d["doc_id"]))
    for i, d in enumerate(docs, start=1):  # 날짜순으로 id를 다시 매겨 읽기 쉽게
        d["doc_id"] = i
    return {"sector": sectors, "company": companies, "price_daily": prices, "financial_year": fins, "document": docs}
