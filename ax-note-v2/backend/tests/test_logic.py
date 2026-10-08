"""DB·SQL·분석 로직 테스트 (pytest). FastAPI 없이 SQLite 만으로 실행돼요: pytest backend/tests/test_logic.py"""
import sqlite3
import statistics
from datetime import date, timedelta

import pytest

from app import events
from app.repo import Repo
from app.seed_data import generate


def test_seed_shapes():
    d = generate()
    assert len(d["company"]) == 8 and len(d["price_daily"]) == 8 * 250 and len(d["financial_year"]) == 8 * 5
    assert all(x["doc_type"] == "filing" for x in d["document"])  # 수집 문서는 공시뿐(뉴스는 사용자가 직접 추가)
    for p in d["price_daily"]:  # 고가/저가가 시가·종가를 감싸는지(DB CHECK 와 같은 규칙)
        assert p["low"] <= min(p["open"], p["close"]) and p["high"] >= max(p["open"], p["close"])


def test_constraints_reject_bad_rows(conn):
    with pytest.raises(sqlite3.IntegrityError):  # 같은 날 시세 중복
        conn.execute("INSERT INTO price_daily(company_id, trade_date, open, high, low, close, volume) "
                     "SELECT company_id, trade_date, open, high, low, close, volume FROM price_daily LIMIT 1")
    with pytest.raises(sqlite3.IntegrityError):  # 근거는 문서/주가 중 정확히 하나
        conn.execute("INSERT INTO note(client_id, company_id, title, created_at, updated_at) VALUES ('t', 1, 'x', '2026-01-01', '2026-01-01')")
        nid = conn.execute("SELECT MAX(note_id) FROM note").fetchone()[0]
        conn.execute("INSERT INTO note_evidence(note_id, doc_id, price_id) VALUES (?, 1, 1)", (nid,))
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):  # 내 자료(news)는 주인이 있어야 해요
        conn.execute("INSERT INTO document(company_id, doc_type, title, source, published_date) VALUES (1, 'news', 'x', 's', '2026-01-01')")
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):  # 수집 공시는 주인이 없어야 해요
        conn.execute("INSERT INTO document(company_id, doc_type, title, source, published_date, created_by) VALUES (1, 'filing', 'x', 's', '2026-01-01', 'me')")
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):  # 같은 접수번호 공시 중복
        conn.execute("INSERT INTO document(company_id, doc_type, title, source, published_date, rcept_no) "
                     "SELECT company_id, 'filing', title, source, published_date, rcept_no FROM document LIMIT 1")
    conn.rollback()


def test_cascade_delete_note_and_document(empty):
    from conftest import load_sample

    c = load_sample(empty)
    c.execute("INSERT INTO note(client_id, company_id, title, created_at, updated_at) VALUES ('t', 1, 'x', '2026-01-01', '2026-01-01')")
    nid = c.execute("SELECT MAX(note_id) FROM note").fetchone()[0]
    c.execute("INSERT INTO note_evidence(note_id, doc_id) VALUES (?, 1)", (nid,))
    c.execute("DELETE FROM note WHERE note_id = ?", (nid,))
    assert c.execute("SELECT COUNT(*) FROM note_evidence").fetchone()[0] == 0  # 노트를 지우면 근거도 같이 지워져요


def test_movers_use_window_function(repo):
    cid = repo.company("005930")["company_id"]
    today = repo.latest_date(cid)
    movers = repo.movers(cid, today - timedelta(days=365), 4.0)
    assert 6 <= len(movers) <= 12
    assert all(abs(m["ret_pct"]) >= 4.0 for m in movers)
    s = {r["trade_date"]: r["close"] for r in repo.series(cid, today - timedelta(days=400))}
    m = movers[-1]
    prev = max(d for d in s if d < m["trade_date"])
    assert m["ret_pct"] == pytest.approx((s[m["trade_date"]] / s[prev] - 1) * 100)  # 손으로 계산한 값과 같아요


def test_every_event_has_linked_filing(repo):
    for code in ("005930", "000660", "373220"):
        c = repo.company(code)
        today = repo.latest_date(c["company_id"])
        movers = repo.movers(c["company_id"], today - timedelta(days=365), 4.0)
        docs = repo.documents(c["company_id"], today - timedelta(days=370))
        linked = events.link_movers(movers, docs)
        assert movers and all(item["docs"] for item in linked)
        for item in linked:
            for d in item["docs"]:
                assert -1 <= (item["mover"]["trade_date"] - d["published_date"]).days <= 3


def test_link_prefers_closest_and_filing_over_user_note():
    mover = {"trade_date": date(2026, 3, 10)}
    docs = [{"doc_id": 1, "doc_type": "news", "published_date": date(2026, 3, 10)},
            {"doc_id": 2, "doc_type": "filing", "published_date": date(2026, 3, 10)},
            {"doc_id": 3, "doc_type": "filing", "published_date": date(2026, 3, 8)},
            {"doc_id": 4, "doc_type": "filing", "published_date": date(2026, 3, 11)},   # 하루 뒤 공시도 후보
            {"doc_id": 5, "doc_type": "filing", "published_date": date(2026, 2, 1)}]    # 너무 먼 문서는 제외
    got = [d["doc_id"] for d in events.link_movers([mover], docs, limit=5)[0]["docs"]]
    assert got == [2, 1, 4, 3]


def test_analysis_matches_independent_python_calculation(repo):
    c = repo.company("000660")
    a = repo.analysis(c["company_id"])
    closes = [r["close"] for r in repo.series(c["company_id"], date(2000, 1, 1))]
    assert a["close"] == closes[-1]
    assert a["returns"]["1개월"] == pytest.approx((closes[-1] / closes[-1 - 21] - 1) * 100, abs=0.01)
    assert a["returns"]["6개월"] == pytest.approx((closes[-1] / closes[-1 - 126] - 1) * 100, abs=0.01)
    ma = statistics.fmean(closes[-120:])
    assert a["ma120_gap"] == pytest.approx((closes[-1] / ma - 1) * 100, abs=0.01)
    peak, mdd = 0, 0
    for x in closes:
        peak = max(peak, x)
        mdd = min(mdd, (x / peak - 1) * 100)
    assert a["mdd"] == pytest.approx(mdd, abs=0.01)
    assert a["volatility_daily"] is not None and 0.3 < a["volatility_daily"] < 6


def test_mdd_hand_calculation(empty):
    empty.execute("INSERT INTO sector(name) VALUES ('s')")
    empty.execute("INSERT INTO company(code, name, market, sector_id) VALUES ('1', 'a', 'KOSPI', 1)")
    for i, c in enumerate([100, 120, 90, 110]):  # 최고 120 → 90 이면 -25%
        empty.execute("INSERT INTO price_daily(company_id, trade_date, open, high, low, close, volume) VALUES (1, ?, ?, ?, ?, ?, 10)",
                      ((date(2026, 1, 1) + timedelta(days=i)).isoformat(), c, c, c, c))
    r = Repo(lambda q, p: [dict(x) for x in empty.execute(q, p).fetchall()])
    a = r.analysis(1)
    assert a["mdd"] == -25.0 and a["ma120"] is None and a["returns"]["1개월"] is None  # 데이터가 모자라면 None


def test_financial_growth_and_peer_rank(repo):
    c = repo.company("005930")
    fins = repo.financials(c["company_id"], 5)
    assert [f["fiscal_year"] for f in fins] == [2025, 2024, 2023, 2022, 2021] and fins[-1]["rev_growth"] is None
    assert fins[0]["rev_growth"] == pytest.approx((fins[0]["revenue"] / fins[1]["revenue"] - 1) * 100, abs=0.1)
    assert fins[0]["op_margin"] == pytest.approx(fins[0]["operating_profit"] / fins[0]["revenue"] * 100, abs=0.1)
    peers = repo.peers(c["company_id"])
    assert {p["code"] for p in peers} == {"005930", "000660"} and peers[0]["margin_rank"] == 1 and peers[0]["n"] == 2
    assert peers[0]["avg_margin"] == pytest.approx(statistics.fmean(p["op_margin"] for p in peers), abs=0.1)
    best = max(peers, key=lambda p: p["op_margin"])
    assert peers[0]["code"] == best["code"]


def test_user_documents_are_private(conn, repo):
    c = repo.company("005930")["company_id"]
    conn.execute("INSERT INTO document(company_id, doc_type, title, source, published_date, created_by, url) VALUES (?, 'news', '내 메모', '직접 입력', '2026-10-01', 'userA', 'https://example.com')", (c,))
    conn.commit()
    since = date(2026, 9, 1)
    titles = lambda client: {d["title"] for d in Repo(repo._run, client=client).documents(c, since)}
    assert "내 메모" in titles("userA") and "내 메모" not in titles("userB") and "내 메모" not in titles("")
