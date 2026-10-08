"""진입 신호 SQL(윈도 함수)을 같은 데이터에 대한 독립적인 파이썬 계산과 맞춰 보고, 매매 시뮬레이션을 손계산과 대조해요."""
import pytest

from app import sql
from app.strategy import FEE_RATE, describe_rule, signal_sql, simulate, summarize


def closes(db, cid):
    return [(r["d"][:10], r["close"]) for r in db.all(sql.SERIES, cid=cid, since="1900-01-01")]


def test_seed_shapes(db):
    assert len(db.all(sql.COMPANIES, like="%")) == 8
    assert db.one("SELECT COUNT(*) AS n FROM price_daily")["n"] == 8 * 500


def test_ma_cross_signals_match_python(db):
    n = 20
    for cid in range(1, 9):
        s = closes(db, cid)
        want = []
        for i in range(n, len(s)):  # i-1 번째에도 20일치가 있어야 어제 값과 비교할 수 있어요
            ma = sum(c for _, c in s[i - n + 1:i + 1]) / n
            pma = sum(c for _, c in s[i - n:i]) / n
            if s[i - 1][1] <= pma and s[i][1] > ma:
                want.append(s[i][0])
        got = [r["trade_date"][:10] for r in db.all(signal_sql("ma_cross", n), cid=cid)]
        assert got == want
    assert want or any(db.all(signal_sql("ma_cross", n), cid=c) for c in range(1, 9))  # 신호가 아예 없는 데이터는 아니어야 해요


def test_dip_buy_signals_match_python(db):
    total = 0
    for cid in range(1, 9):
        s = closes(db, cid)
        want = [s[i][0] for i in range(1, len(s)) if (s[i][1] - s[i - 1][1]) / s[i - 1][1] * 100 <= -4.0]
        got = [r["trade_date"][:10] for r in db.all(signal_sql("dip_buy", 4), cid=cid)]
        assert got == want
        total += len(got)
    assert total > 0


def test_breakout_signals_match_python(db):
    n, total = 20, 0
    for cid in range(1, 9):
        s = closes(db, cid)
        want = [s[i][0] for i in range(n, len(s)) if s[i][1] > max(c for _, c in s[i - n:i])]
        got = [r["trade_date"][:10] for r in db.all(signal_sql("breakout", n), cid=cid)]
        assert got == want
        total += len(got)
    assert total > 0


def test_signal_sql_all_companies_and_latest_only(db):
    all_rows = db.all(signal_sql("dip_buy", 2, single=False))
    assert {r["company_id"] for r in all_rows} <= set(range(1, 9)) and len({r["company_id"] for r in all_rows}) > 1
    last = {r["company_id"]: r["d"] for r in db.all("SELECT company_id, MAX(trade_date) AS d FROM price_daily GROUP BY company_id")}
    for r in db.all(signal_sql("dip_buy", 0.0001 + 1, single=False, latest_only=True)):
        assert r["trade_date"] == last[r["company_id"]]


def test_signal_sql_rejects_bad_params():
    with pytest.raises(ValueError):
        signal_sql("ma_cross", 1)
    with pytest.raises(ValueError):
        signal_sql("nope", 5)


# ───── 매매 시뮬레이션 (손으로 만든 시세) ─────
def S(*rows):
    return [{"d": f"2026-01-{i + 1:02d}", "open": o, "close": c} for i, (o, c) in enumerate(rows)]


def test_simulate_enters_next_day_open_and_takes_profit():
    s = S((100, 100), (100, 100), (100, 103), (100, 112), (110, 120))  # 1/1 신호 → 1/2 시가 100 매수, 1/4 종가 112 에서 +10% 익절
    t = simulate(s, ["2026-01-01"], take_profit=10, stop_loss=5, max_hold=10, fee_rate=0)
    assert len(t) == 1 and t[0]["entry_date"] == "2026-01-02" and t[0]["entry_price"] == 100
    assert t[0]["exit_date"] == "2026-01-04" and t[0]["exit_reason"] == "tp" and t[0]["return_pct"] == 12.0 and t[0]["hold_days"] == 2


def test_simulate_stop_loss_time_exit_and_end():
    sl = simulate(S((100, 100), (100, 100), (100, 94), (100, 90)), ["2026-01-01"], 50, 5, 10, 0)
    assert sl[0]["exit_reason"] == "sl" and sl[0]["exit_date"] == "2026-01-03" and sl[0]["return_pct"] == -6.0
    tm = simulate(S((100, 100), (100, 100), (100, 101), (100, 102), (100, 101)), ["2026-01-01"], 50, 50, 2, 0)
    assert tm[0]["exit_reason"] == "time" and tm[0]["exit_date"] == "2026-01-04" and tm[0]["hold_days"] == 2
    end = simulate(S((100, 100), (100, 100), (100, 101)), ["2026-01-01"], 50, 50, 10, 0)
    assert end[0]["exit_reason"] == "end" and end[0]["exit_date"] == "2026-01-03"


def test_simulate_ignores_signals_while_holding_and_skips_last_day():
    s = S((100, 100), (100, 100), (100, 101), (100, 120), (100, 100), (100, 100))
    got = simulate(s, ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-06"], 15, 50, 10, 0)
    # 1/1 신호 → 1/2 매수 → 1/4 익절(+20%). 1/2·1/3 신호는 보유 중이라 무시. 1/6 은 마지막 날이라 다음 날이 없어 못 사요.
    assert [(t["entry_date"], t["exit_date"]) for t in got] == [("2026-01-02", "2026-01-04")]
    # 팔린 날(1/4)에 난 신호는 다음 날 다시 살 수 있어요
    again = simulate(s, ["2026-01-01", "2026-01-04"], 15, 50, 10, 0)
    assert [t["entry_date"] for t in again] == ["2026-01-02", "2026-01-05"]


def test_simulate_fee_and_start_filter():
    s = S((100, 100), (100, 100), (100, 110))
    t = simulate(s, ["2026-01-01"], 5, 5, 5, fee_rate=FEE_RATE)[0]
    assert t["return_pct"] == pytest.approx(((110 * 0.999) / (100 * 1.001) - 1) * 100, abs=0.006)
    assert simulate(s, ["2026-01-01"], 5, 5, 5, 0, start="2026-01-02") == []


def test_summarize_hand_calculated():
    trades = [{"return_pct": 10.0, "hold_days": 2}, {"return_pct": -20.0, "hold_days": 4}, {"return_pct": 5.0, "hold_days": 3}]
    s = summarize(trades, [{"close": 100}, {"close": 130}])
    assert s["trade_count"] == 3 and s["win_count"] == 2 and s["win_rate"] == 66.7 and s["avg_return"] == pytest.approx(-1.67, abs=0.01)
    assert s["total_return"] == pytest.approx((1.10 * 0.80 * 1.05 - 1) * 100, abs=0.01)  # 복리 -7.6%
    assert s["mdd"] == -20.0 and s["benchmark_return"] == 30.0 and s["avg_hold_days"] == 3.0
    assert summarize([], [{"close": 100}, {"close": 90}])["avg_return"] is None


def test_describe_rule():
    r = {"entry_type": "ma_cross", "entry_param": 20.0, "take_profit_pct": 8.0, "stop_loss_pct": 4.0, "max_hold_days": 20}
    assert describe_rule(r) == "종가가 20일선을 위로 뚫으면 매수 → +8% 익절 / -4% 손절 / 최대 20일 보유"
    assert "3.5% 이상 떨어지면" in describe_rule({**r, "entry_type": "dip_buy", "entry_param": 3.5})
