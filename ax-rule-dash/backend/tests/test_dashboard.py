"""대시보드 SQL(윈도 함수·GROUP BY·RANK)을 같은 데이터에 대한 독립적인 파이썬 계산과 맞춰 보고, 점수를 손계산과 대조해요."""
import pytest

from app import service as S
from app import sql
from app.scoring import score_rows


def series(conn, cid):
    return [dict(r) for r in conn.execute("SELECT trade_date, close, volume FROM price_daily WHERE company_id = ? ORDER BY trade_date", (cid,))]


def test_dashboard_rows_match_python(conn, db):
    rows = {r["company_id"]: r for r in db.all(sql.DASH_ROWS)}
    assert len(rows) == 8
    for cid, r in rows.items():
        s = series(conn, cid)
        c = [x["close"] for x in s]
        assert r["trade_date"][:10] == s[-1]["trade_date"] and r["close"] == c[-1]
        assert r["chg"] == pytest.approx((c[-1] / c[-2] - 1) * 100, abs=1e-6)
        assert r["r1m"] == pytest.approx((c[-1] / c[-22] - 1) * 100, abs=1e-6)
        assert r["r3m"] == pytest.approx((c[-1] / c[-64] - 1) * 100, abs=1e-6)
        assert r["r6m"] == pytest.approx((c[-1] / c[-127] - 1) * 100, abs=1e-6)
        assert r["ma_gap"] == pytest.approx((c[-1] / (sum(c[-120:]) / 120) - 1) * 100, abs=1e-6)
        v = [x["volume"] for x in s]
        assert r["vol_ratio"] == pytest.approx(v[-1] / (sum(v[-21:-1]) / 20), abs=1e-9)  # 오늘 거래량 ÷ 직전 20일 평균
        f = conn.execute("SELECT per, pbr FROM fundamental_daily WHERE company_id = ? ORDER BY trade_date DESC LIMIT 1", (cid,)).fetchone()
        assert (r["per"], r["pbr"]) == (f["per"], f["pbr"])
        y = conn.execute("SELECT fiscal_year, revenue, operating_profit FROM financial_year WHERE company_id = ? ORDER BY fiscal_year DESC LIMIT 2", (cid,)).fetchall()
        assert r["fiscal_year"] == y[0]["fiscal_year"] == 2025
        assert r["op_margin"] == pytest.approx(y[0]["operating_profit"] / y[0]["revenue"] * 100, abs=1e-9)
        assert r["rev_growth"] == pytest.approx((y[0]["revenue"] / y[1]["revenue"] - 1) * 100, abs=1e-9)


def test_sector_agg_is_group_average(db):
    rows = db.all(sql.DASH_ROWS)
    agg = {a["sector"]: a for a in db.all(sql.SECTOR_AGG)}
    assert set(agg) == {r["sector"] for r in rows}
    for sec, a in agg.items():
        mine = [r for r in rows if r["sector"] == sec]
        assert a["n"] == len(mine)
        assert a["avg_r3m"] == pytest.approx(sum(r["r3m"] for r in mine) / len(mine), abs=1e-9)
        assert a["avg_per"] == pytest.approx(sum(r["per"] for r in mine) / len(mine), abs=1e-9)
    assert [a["avg_r3m"] for a in db.all(sql.SECTOR_AGG)] == sorted((a["avg_r3m"] for a in agg.values()), reverse=True)


def test_dashboard_summary(db):
    d = S.dashboard(db)
    s = d["summary"]
    assert s["count"] == 8 and s["up"] + s["down"] + s["flat"] == 8 and s["last_date"] == "2026-10-07"
    assert s["up"] == sum(1 for r in d["rows"] if r["chg"] > 0)
    assert all(0 <= r["score"] <= 100 for r in d["rows"])


def test_score_hand_calculated():
    rows = [
        {"code": "A", "r3m": 10.0, "ma_gap": 5.0, "per": 8.0, "op_margin": 20.0, "rev_growth": 10.0},
        {"code": "B", "r3m": 0.0, "ma_gap": 5.0, "per": 12.0, "op_margin": 10.0, "rev_growth": None},
        {"code": "C", "r3m": -10.0, "ma_gap": -5.0, "per": None, "op_margin": 5.0, "rev_growth": 5.0},
    ]
    a, b, c = score_rows(rows)
    # A: 모멘텀 1등(20) + 추세 B와 공동 1등(평균 0.75 → 15) + 가치 PER 최저(20, C는 순위 제외) + 수익성 20 + 성장 1등(20) = 95
    assert a["score_parts"]["trend"]["points"] == 15.0 and a["score"] == 95
    # B: 모멘텀 10 + 추세 15 + 가치 0(PER 더 높음) + 수익성 10 + 성장 데이터 없음 10 = 45
    assert b["score"] == 45 and b["score_parts"]["growth"]["note"].startswith("데이터 없음")
    # C: 0 + 0 + 0(PER 없음) + 0 + 0(성장 꼴찌) = 0
    assert c["score"] == 0 and "PER" in c["score_parts"]["value"]["note"]


def test_score_handles_missing_company_data(conn, db):
    """시세가 짧고 재무·PER 이 없는 신규 종목: 120일선 괴리·재무가 비고, 점수는 규칙대로(가치 0, 데이터 없는 기준 10)."""
    conn.execute("INSERT INTO company(code,name,market,sector_id) VALUES ('999999','신규상장','KOSDAQ',1)")
    cid = conn.execute("SELECT company_id FROM company WHERE code='999999'").fetchone()[0]
    days = [r["d"][:10] for r in S.prices(db, "005930", 60)][-30:]
    for i, d in enumerate(days):
        conn.execute("INSERT INTO price_daily(company_id,trade_date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,1000)", (cid, d, 100 + i, 100 + i, 100 + i, 100 + i))
    conn.commit()
    row = next(r for r in S.dashboard(db)["rows"] if r["code"] == "999999")
    assert row["ma_gap"] is None and row["r3m"] is None and row["per"] is None and row["op_margin"] is None and row["r1m"] is not None
    p = row["score_parts"]
    assert p["value"]["points"] == 0 and p["momentum"]["points"] == 10 and p["profit"]["points"] == 10


def test_company_analysis_mdd_and_volatility(conn, db):
    a = S.company_analysis(db, "005930")
    s = series(conn, 1)
    year = [x["close"] for x in s if x["trade_date"] >= "2025-10-07"]
    peak, mdd = year[0], 0.0
    for x in year:
        peak = max(peak, x)
        mdd = min(mdd, (x / peak - 1) * 100)
    assert a["mdd"] == pytest.approx(mdd, abs=0.01)
    c = [x["close"] for x in s]
    rets = [(c[i] / c[i - 1] - 1) * 100 for i in range(1, len(c)) if s[i]["trade_date"] >= "2026-07-09"]
    m = sum(rets) / len(rets)
    sd = (sum((x - m) ** 2 for x in rets) / (len(rets) - 1)) ** 0.5
    assert a["volatility_daily"] == pytest.approx(sd, abs=0.01)
    assert set(a["returns"]) == {"1개월", "3개월", "6개월"} and a["score_pool"] == 8
    with pytest.raises(S.ServiceError):
        S.company_analysis(db, "000000")


def test_financials_growth_and_peer_rank(conn, db):
    fins = S.company_financials(db, "005930")
    assert [f["fiscal_year"] for f in fins] == [2025, 2024, 2023, 2022, 2021] and fins[-1]["rev_growth"] is None
    assert fins[0]["rev_growth"] == round((fins[0]["revenue"] / fins[1]["revenue"] - 1) * 100, 1)
    peers = S.company_peers(db, "005930")
    assert {p["code"] for p in peers} == {"005930", "000660"}
    margins = sorted((p["op_margin"] for p in peers), reverse=True)
    assert [p["op_margin"] for p in peers if p["margin_rank"] == 1] == [margins[0]]
    assert abs(peers[0]["avg_margin"] - sum(p["op_margin"] for p in peers) / 2) < 0.06  # 반올림 전 값의 평균이라 0.05 안쪽 차이


def test_fundamental_series_and_monthly(db):
    f = S.company_fundamentals(db, "005930", 30)
    assert 15 <= len(f) <= 25 and all(x["per"] > 0 for x in f)
    m = S.company_monthly(db, "005930")
    assert len(m) >= 23 and all(x["low"] <= x["avg_close"] <= x["high"] for x in m)
