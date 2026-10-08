"""API 테스트 (FastAPI TestClient). pip install pytest httpx 후:  pytest backend/tests/test_api.py
임시 SQLite 파일을 쓰도록 DATABASE_URL 을 먼저 정해요.
⚠️ 이 파일은 작성 환경에 FastAPI 를 설치할 수 없어 실행해 보지 못했어요. 로직 자체는 test_service.py 가 같은 함수로 검증해요."""
import os
import pathlib
import sys
import tempfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

A = {"X-Client-Id": "tester-a"}
B = {"X-Client-Id": "tester-b"}
RULE = {"name": "20일선 돌파", "entry_type": "ma_cross", "entry_param": 20, "take_profit_pct": 8, "stop_loss_pct": 4, "max_hold_days": 20}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # with 문이 lifespan(테이블 생성+샘플 데이터)을 실행해요
        yield c


def test_status_and_companies(client):
    s = client.get("/api/status").json()
    assert s["is_sample"] is True and s["counts"]["company"] == 8
    assert len(client.get("/api/companies").json()) == 8
    assert [c["code"] for c in client.get("/api/companies", params={"q": "하이닉스"}).json()] == ["000660"]
    assert client.get("/api/companies/999999").status_code == 404
    assert len(client.get("/api/companies/005930/prices", params={"days": 100}).json()) > 50


def test_dashboard_and_company_analysis(client):
    d = client.get("/api/dashboard").json()
    assert d["summary"]["count"] == 8 and len(d["rows"]) == 8 and len(d["sectors"]) == 5
    assert all(0 <= r["score"] <= 100 for r in d["rows"])
    a = client.get("/api/companies/005930/analysis").json()
    assert set(a["returns"]) == {"1개월", "3개월", "6개월"} and a["per"] > 0 and len(a["score_parts"]) == 5
    assert len(client.get("/api/companies/005930/financials").json()) == 5
    assert {p["code"] for p in client.get("/api/companies/005930/peers").json()} == {"005930", "000660"}
    assert len(client.get("/api/companies/005930/fundamentals", params={"days": 30}).json()) > 10
    assert client.get("/api/companies/999999/analysis").status_code == 404


def test_requires_client_id(client):
    assert client.get("/api/rules").status_code == 400
    assert client.get("/api/accounts").status_code == 400


def test_rule_backtest_flow_and_privacy(client):
    r = client.post("/api/rules", json=RULE, headers=A)
    assert r.status_code == 201
    rid = r.json()["rule_id"]
    assert client.post("/api/rules", json=RULE, headers=A).status_code == 409
    assert client.post("/api/rules", json={**RULE, "name": "x", "entry_param": 1}, headers=A).status_code == 422
    assert client.get(f"/api/rules/{rid}", headers=B).status_code == 404
    run = client.post(f"/api/rules/{rid}/backtests", json={"company_code": "005930", "period": "1y"}, headers=A)
    assert run.status_code == 201 and run.json()["trade_count"] == len(run.json()["trades"])
    assert client.get(f"/api/backtests/{run.json()['run_id']}", headers=B).status_code == 404
    assert client.get(f"/api/rules/{rid}/report", headers=A).json()["backtest"]["trade_count"] == run.json()["trade_count"]
    assert client.get("/api/signals", headers=A).status_code == 200
    assert client.delete(f"/api/rules/{rid}", headers=A).status_code == 204
    assert client.get(f"/api/backtests/{run.json()['run_id']}", headers=A).status_code == 404  # CASCADE


def test_account_and_trade_flow(client):
    acc = client.post("/api/accounts", json={"name": "내 계좌", "initial_cash": 10_000_000}, headers=A)
    assert acc.status_code == 201
    aid = acc.json()["account_id"]
    date = client.get("/api/companies/005930/prices", params={"days": 30}).json()[-1]["d"]
    t = client.post(f"/api/accounts/{aid}/trades", json={"code": "005930", "side": "buy", "trade_date": date, "qty": 10}, headers=A)
    assert t.status_code == 201 and t.json()["fee"] > 0
    over = client.post(f"/api/accounts/{aid}/trades", json={"code": "005930", "side": "sell", "trade_date": date, "qty": 11}, headers=A)
    assert over.status_code == 409
    d = client.get(f"/api/accounts/{aid}", headers=A).json()
    assert d["audit"] == {"cash_ok": True, "holdings_ok": True} and d["holdings"][0]["qty"] == 10
    assert client.get(f"/api/accounts/{aid}", headers=B).status_code == 404
    assert client.put(f"/api/accounts/{aid}/trades/{t.json()['trade_id']}", json={"memo": "메모"}, headers=A).json()["memo"] == "메모"
    assert client.get("/api/companies/005930/my-trades", headers=A).json()[0]["qty"] == 10
    assert client.delete(f"/api/accounts/{aid}/trades/{t.json()['trade_id']}", headers=A).status_code == 204
    assert client.delete(f"/api/accounts/{aid}", headers=A).status_code == 204


def test_web_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "종목 분석" in r.text
    assert client.get("/app.js").status_code == 200
