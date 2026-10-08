"""급등락일 ↔ 공시 연결. 주가가 크게 움직인 날(SQL LAG로 찾음) 전 3일부터 다음 날까지 나온 문서를 붙여요."""

MOVE_THRESHOLD = 4.0  # 하루 등락률이 이 값(%) 이상이면 "급등락일"


def link_movers(movers: list, docs: list, limit: int = 3) -> list:
    """급등락일마다 가까운 날짜의 문서를 골라요. 공시는 장 마감 뒤에 나오기도 해서 '다음 날'(gap=-1)까지 봐요."""
    linked = []
    for m in movers:
        near = []
        for d in docs:
            gap = (m["trade_date"] - d["published_date"]).days  # 0 = 같은 날, 양수 = 공시가 먼저, -1 = 하루 뒤
            if -1 <= gap <= 3:
                near.append((abs(gap) if gap >= 0 else 0.5, d["doc_type"] != "filing", d["doc_id"], d))
        near.sort(key=lambda x: x[:3])
        linked.append({"mover": m, "docs": [x[3] for x in near[:limit]]})
    return linked
