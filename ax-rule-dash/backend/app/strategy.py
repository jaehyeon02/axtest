"""규칙(진입 조건 + 청산 조건)을 과거 시세에 적용하는 백테스트 계산.

역할 나누기
  - 진입 신호  : SQL 윈도 함수로 구해요 (signal_sql). 이동평균·직전 종가·직전 N일 최고가를 DB 가 계산.
  - 매매 흐름  : 파이썬(simulate). "들고 있는 동안 다음 신호는 무시"처럼 앞 거래의 결과가 다음 거래에 영향을
                 주는 순차 로직이라 SQL 한 문장보다 코드가 읽기 쉬워서 나눴어요.
  - 요약 통계  : 파이썬(summarize).

현실과 가깝게 하려고 두 가지를 지켜요.
  1. 신호가 난 날의 **다음 거래일 시가**에 사요. (신호를 본 당일 종가에 샀다고 치면 미래를 미리 아는 반칙이에요.)
  2. 수수료(FEE_RATE)를 사고팔 때 모두 반영해요. 모의투자 장부와 같은 값이라 결과를 서로 비교할 수 있어요.
"""
FEE_RATE = 0.001  # 거래대금의 0.1% (매수·매도 각각)

ENTRY_TYPES = {
    "ma_cross": "이동평균선 상향 돌파",
    "dip_buy": "급락일 매수",
    "breakout": "신고가 돌파",
}
REASON_TEXT = {"tp": "익절", "sl": "손절", "time": "보유기간 만료", "end": "데이터 끝"}


def describe_rule(r: dict) -> str:
    p = r["entry_param"]
    p_int, p_txt = int(round(p)), f"{p:g}"
    entry = {
        "ma_cross": f"종가가 {p_int}일선을 위로 뚫으면 매수",
        "dip_buy": f"하루 {p_txt}% 이상 떨어지면 매수",
        "breakout": f"종가가 직전 {p_int}일 최고가를 넘으면 매수",
    }[r["entry_type"]]
    return f"{entry} → +{r['take_profit_pct']:g}% 익절 / -{r['stop_loss_pct']:g}% 손절 / 최대 {r['max_hold_days']}일 보유"


def signal_sql(entry_type: str, param: float, single: bool = True, latest_only: bool = False) -> str:
    """진입 신호가 난 (company_id, trade_date) 를 돌려주는 SQL.

    single=True  : :cid 한 종목만.   single=False: 전체 종목.
    latest_only  : 각 종목의 가장 최근 거래일에 신호가 난 것만 ("오늘의 신호").
    param 은 숫자로 검증된 값이라 문장에 직접 넣어요(윈도 프레임의 크기는 파라미터 바인딩이 DB마다 달라서).
    """
    where = "WHERE company_id = :cid" if single else ""
    part = "PARTITION BY company_id ORDER BY trade_date"
    if entry_type == "ma_cross":
        n = int(param)
        if n < 2:
            raise ValueError("이동평균 기간은 2일 이상이어야 해요.")
        frame = f"ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW"
        inner = f"""SELECT company_id, trade_date, close,
       AVG(close)   OVER ({part} {frame}) AS ma,
       COUNT(close) OVER ({part} {frame}) AS cnt
FROM price_daily {where}"""
        mid = f"""SELECT company_id, trade_date, close, ma, cnt,
       LAG(close) OVER ({part}) AS pc, LAG(ma) OVER ({part}) AS pma, LAG(cnt) OVER ({part}) AS pcnt
FROM ({inner}) a"""
        cond = f"cnt = {n} AND pcnt = {n} AND pc <= pma AND close > ma"  # N일치가 다 쌓인 날만, 어제까지 선 아래 → 오늘 선 위
    elif entry_type == "dip_buy":
        x = float(param)
        mid = f"""SELECT company_id, trade_date, close, LAG(close) OVER ({part}) AS pc FROM price_daily {where}"""
        cond = f"pc IS NOT NULL AND (close - pc) * 100.0 / pc <= -{x:.4f}"
    elif entry_type == "breakout":
        n = int(param)
        if n < 2:
            raise ValueError("신고가 기준 기간은 2일 이상이어야 해요.")
        frame = f"ROWS BETWEEN {n} PRECEDING AND 1 PRECEDING"  # 오늘을 뺀 직전 N일
        mid = f"""SELECT company_id, trade_date, close,
       MAX(close)   OVER ({part} {frame}) AS hi,
       COUNT(close) OVER ({part} {frame}) AS cnt
FROM price_daily {where}"""
        cond = f"cnt = {n} AND close > hi"
    else:
        raise ValueError(f"알 수 없는 진입 조건: {entry_type}")
    last = "AND trade_date = (SELECT MAX(p.trade_date) FROM price_daily p WHERE p.company_id = b.company_id)" if latest_only else ""
    return f"SELECT company_id, trade_date FROM ({mid}) b WHERE {cond} {last} ORDER BY company_id, trade_date"


def simulate(series: list, signals: list, take_profit: float, stop_loss: float, max_hold: int, fee_rate: float = FEE_RATE, start: str | None = None) -> list:
    """series: [{'d','open','close'}...] 날짜순.  signals: 신호가 난 날짜(문자열) 목록.

    - 신호 다음 거래일 시가에 매수. 매수 다음 날부터 매일 종가로 수익률을 확인:
        +take_profit% 이상 → 익절,  -stop_loss% 이하 → 손절,  max_hold 일 보유 → 만료 청산
      (같은 날 익절·손절 조건이 동시에 맞을 수는 없어요: 종가 하나로 판단하기 때문)
    - 데이터 끝까지 청산 조건이 없으면 마지막 종가로 정리('end').
    - 들고 있는 동안 나온 신호는 무시해요(한 번에 한 포지션).
    """
    idx = {r["d"]: i for i, r in enumerate(series)}
    trades, free = [], 0
    for sd in sorted(signals):
        if start and sd < start:
            continue
        i = idx.get(sd)
        if i is None:
            continue
        e = i + 1
        if e >= len(series) or e < free:  # 다음 거래일이 없거나, 아직 앞 거래가 안 끝났어요
            continue
        entry = series[e]["open"]
        reason, j = "end", e
        for j in range(e + 1, len(series)):
            r = (series[j]["close"] / entry - 1) * 100
            if r >= take_profit:
                reason = "tp"
                break
            if r <= -stop_loss:
                reason = "sl"
                break
            if j - e >= max_hold:
                reason = "time"
                break
        out = series[j]["close"]
        net = ((out * (1 - fee_rate)) / (entry * (1 + fee_rate)) - 1) * 100
        trades.append({"entry_date": series[e]["d"], "entry_price": entry, "exit_date": series[j]["d"], "exit_price": out,
                       "exit_reason": reason, "return_pct": round(net, 2), "hold_days": j - e})
        free = j + 1
    return trades


def summarize(trades: list, series: list) -> dict:
    n = len(trades)
    wins = sum(1 for t in trades if t["return_pct"] > 0)
    eq = peak = 1.0
    mdd = 0.0
    for t in trades:
        eq *= 1 + t["return_pct"] / 100
        peak = max(peak, eq)
        mdd = min(mdd, (eq / peak - 1) * 100)
    bench = (series[-1]["close"] / series[0]["close"] - 1) * 100 if len(series) > 1 else 0.0
    return {
        "trade_count": n,
        "win_count": wins,
        "win_rate": round(wins / n * 100, 1) if n else None,
        "avg_return": round(sum(t["return_pct"] for t in trades) / n, 2) if n else None,
        "total_return": round((eq - 1) * 100, 2) if n else None,
        "mdd": round(mdd, 2) if n else None,
        "avg_hold_days": round(sum(t["hold_days"] for t in trades) / n, 1) if n else None,
        "benchmark_return": round(bench, 2),
    }
