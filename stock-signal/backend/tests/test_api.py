"""기능 테스트 (정상 / 잘못된 데이터 / 존재하지 않는 ID / 빈 데이터).

실행 전제: DB 가 떠 있고(docker compose up -d), 스키마가 적용되어 있을 것.
실행: cd backend && pytest -v
테스트용 종목(코드 999999)·회원(테스트회원)을 만들고 끝나면 삭제한다. 기존 데이터는 건드리지 않는다.
"""
import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
TEST_NAME = "테스트종목"
TEST_NICK = "테스트회원"


@pytest.fixture(scope="module")
def company():
    for old in client.get("/companies", params={"q": TEST_NAME}).json():  # 이전 실패 잔여물 정리
        client.delete(f"/companies/{old['company_id']}")
    market_id = client.get("/markets").json()[0]["market_id"]
    res = client.post("/companies", json={"code": "999999", "name": TEST_NAME, "market_id": market_id})
    assert res.status_code == 201, res.text
    created = res.json()
    yield created
    client.delete(f"/companies/{created['company_id']}")


@pytest.fixture(scope="module")
def member():
    for old in client.get("/members").json():
        if old["nickname"] == TEST_NICK:
            client.delete(f"/members/{old['member_id']}")
    res = client.post("/members", json={"nickname": TEST_NICK})
    assert res.status_code == 201, res.text
    created = res.json()
    yield created
    client.delete(f"/members/{created['member_id']}")


def price_body(company_id, date="2030-01-02", **override):
    body = {
        "company_id": company_id, "trade_date": date,
        "open_price": 100, "high_price": 120, "low_price": 90, "close_price": 110, "volume": 1000,
    }
    body.update(override)
    return body


def trade_body(member_id, company_id, side="BUY", quantity=10, price=1000):
    return {
        "member_id": member_id, "company_id": company_id, "trade_date": "2030-02-01",
        "side": side, "quantity": quantity, "price": price,
    }


# ---------- 상태 / 종목 ----------
def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_company_duplicate_code(company):
    market_id = client.get("/markets").json()[0]["market_id"]
    res = client.post("/companies", json={"code": "999999", "name": "중복", "market_id": market_id})
    assert res.status_code == 409


def test_company_not_found():
    assert client.get("/companies/99999999").status_code == 404


# ---------- 시세 ----------
def test_price_crud(company):
    res = client.post("/prices", json=price_body(company["company_id"]))
    assert res.status_code == 201, res.text
    pid = res.json()["price_id"]
    assert client.put(f"/prices/{pid}", json={"close_price": 115}).json()["close_price"] == 115
    assert client.delete(f"/prices/{pid}").status_code == 204
    assert client.get(f"/prices/{pid}").status_code == 404


def test_price_high_lower_than_low(company):
    res = client.post("/prices", json=price_body(company["company_id"], high_price=50, low_price=90))
    assert res.status_code == 422


def test_price_duplicate_date(company):
    first = client.post("/prices", json=price_body(company["company_id"], date="2030-01-03"))
    assert first.status_code == 201
    try:
        assert client.post("/prices", json=price_body(company["company_id"], date="2030-01-03")).status_code == 409
    finally:
        client.delete(f"/prices/{first.json()['price_id']}")


# ---------- 회원 ----------
def test_member_duplicate_nickname(member):
    assert client.post("/members", json={"nickname": TEST_NICK}).status_code == 409


# ---------- 관심종목 ----------
def test_watchlist_flow(company, member):
    res = client.post("/watchlist", json={"member_id": member["member_id"], "company_id": company["company_id"]})
    assert res.status_code == 201, res.text
    watch_id = res.json()["watch_id"]
    try:
        rows = client.get("/watchlist", params={"member_id": member["member_id"]}).json()
        assert [r["code"] for r in rows] == ["999999"]
        assert "sig_trend" in rows[0]
    finally:
        assert client.delete(f"/watchlist/{watch_id}").status_code == 204


def test_watchlist_duplicate(company, member):
    body = {"member_id": member["member_id"], "company_id": company["company_id"]}
    first = client.post("/watchlist", json=body)
    assert first.status_code == 201
    try:
        assert client.post("/watchlist", json=body).status_code == 409
    finally:
        client.delete(f"/watchlist/{first.json()['watch_id']}")


def test_watchlist_unknown_member():
    assert client.get("/watchlist", params={"member_id": 99999999}).status_code == 404


# ---------- 모의 거래 / 포트폴리오 ----------
def test_portfolio_empty(member):
    data = client.get("/trades/portfolio", params={"member_id": member["member_id"]}).json()
    assert data["holdings"] == [] and data["total"]["market_value"] == 0


def test_trade_oversell(company, member):
    res = client.post("/trades", json=trade_body(member["member_id"], company["company_id"], side="SELL", quantity=1))
    assert res.status_code == 422


def test_trade_invalid_values(company, member):
    assert client.post("/trades", json=trade_body(member["member_id"], company["company_id"], quantity=0)).status_code == 422
    assert client.post("/trades", json=trade_body(member["member_id"], company["company_id"], side="HOLD")).status_code == 422


def test_trade_buy_and_portfolio(company, member):
    cid, mid = company["company_id"], member["member_id"]
    price = client.post("/prices", json=price_body(cid, date="2030-03-01", close_price=1200, high_price=1300, low_price=1100))
    assert price.status_code == 201
    t1 = client.post("/trades", json=trade_body(mid, cid, quantity=10, price=1000))
    t2 = client.post("/trades", json=trade_body(mid, cid, quantity=10, price=1400))
    assert t1.status_code == 201 and t2.status_code == 201
    try:
        data = client.get("/trades/portfolio", params={"member_id": mid}).json()
        row = next(h for h in data["holdings"] if h["code"] == "999999")
        assert row["qty"] == 20 and row["avg_cost"] == 1200  # (10*1000 + 10*1400) / 20
        assert row["close_price"] == 1200 and row["pnl"] == 0
    finally:
        for t in (t1, t2):
            client.delete(f"/trades/{t.json()['trade_id']}")
        client.delete(f"/prices/{price.json()['price_id']}")


def test_trade_delete_buy_blocked(company, member):
    cid, mid = company["company_id"], member["member_id"]
    buy = client.post("/trades", json=trade_body(mid, cid, quantity=10)).json()
    sell = client.post("/trades", json=trade_body(mid, cid, side="SELL", quantity=5)).json()
    try:
        assert client.delete(f"/trades/{buy['trade_id']}").status_code == 409
    finally:
        client.delete(f"/trades/{sell['trade_id']}")
        client.delete(f"/trades/{buy['trade_id']}")


# ---------- 신호등 ----------
def test_signal_no_prices(company):
    res = client.get("/signals/999999")
    assert res.status_code == 200 and res.json()["close_price"] is None


def test_signal_unknown_code():
    assert client.get("/signals/ZZZZZZ").status_code == 404


def test_signal_with_prices(company):
    cid = company["company_id"]
    start = dt.date(2029, 1, 1)
    ids = []
    for i in range(70):  # 70일: 60일 평균까지 계산 가능
        day = start + dt.timedelta(days=i)
        close = 1000 + i * 10  # 꾸준한 상승
        res = client.post("/prices", json=price_body(cid, date=day.isoformat(), open_price=close, high_price=close + 5,
                                                     low_price=close - 5, close_price=close))
        assert res.status_code == 201, res.text
        ids.append(res.json()["price_id"])
    try:
        sig = client.get("/signals/999999").json()
        assert sig["ma5"] and sig["ma20"] and sig["ma60"]
        assert sig["ma5"] > sig["ma20"] > sig["ma60"] and sig["sig_trend"] == "good"
        assert len(client.get("/signals/999999/series", params={"limit": 10}).json()) == 10
    finally:
        for pid in ids:
            client.delete(f"/prices/{pid}")


def test_compare_needs_two():
    assert client.get("/signals/compare", params={"codes": "005930"}).status_code == 422
