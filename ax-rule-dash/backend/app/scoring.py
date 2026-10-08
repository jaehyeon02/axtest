"""규칙 기반 종합 점수(0~100). AI 가 아니라 "누구나 계산을 따라가 볼 수 있는" 투명한 점수예요.

다섯 가지 기준을 각각 0~20점으로 채점해서 더해요. 점수는 **지금 비교 대상인 종목들 사이의 순위(백분위)** 로 정해요.
  모멘텀  3개월 수익률이 높을수록      추세  120일선 위로 멀수록
  가치    PER 이 낮을수록(적자·계산불가는 0점)   수익성  영업이익률이 높을수록   성장  매출 성장률이 높을수록
값이 없는 기준(데이터 부족)은 중간점 10점을 주고 화면에 "데이터 없음"으로 표시해요. 투자 추천이 아니에요.
"""
CRITERIA = [
    ("momentum", "모멘텀", "r3m", True),
    ("trend", "추세", "ma_gap", True),
    ("value", "가치", "per", False),
    ("profit", "수익성", "op_margin", True),
    ("growth", "성장", "rev_growth", True),
]
MAX_PER_CRITERION = 20.0


def _percentile(value, values, higher_is_better):
    """values 안에서 value 가 얼마나 좋은 쪽인지 0~1. 동점은 중간으로 처리해요."""
    m = len(values)
    if m < 2:
        return 0.5
    less = sum(1 for v in values if (v < value if higher_is_better else v > value))
    same = sum(1 for v in values if v == value)
    return (less + (same - 1) / 2) / (m - 1)


def score_rows(rows: list) -> list:
    """rows: DASH_ROWS 결과. 각 행에 score(0~100)와 score_parts({키: {label, points, note}})를 붙여서 돌려줘요."""
    pools = {}
    for key, _label, col, _hi in CRITERIA:
        vals = [r[col] for r in rows if r.get(col) is not None]
        if key == "value":
            vals = [v for v in vals if v > 0]  # PER 이 0 이하(적자)면 순위에서 빼요
        pools[key] = vals
    out = []
    for r in rows:
        parts, total = {}, 0.0
        for key, label, col, hi in CRITERIA:
            v = r.get(col)
            if key == "value" and (v is None or v <= 0):
                pts, note = 0.0, "적자이거나 PER 계산 불가"
            elif v is None:
                pts, note = MAX_PER_CRITERION / 2, "데이터 없음(중간점)"
            else:
                pts, note = round(MAX_PER_CRITERION * _percentile(v, pools[key], hi), 1), ""
            parts[key] = {"label": label, "points": pts, "note": note, "value": v}
            total += pts
        out.append({**r, "score": round(total), "score_parts": parts})
    return out
