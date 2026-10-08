"""기능 테스트 (정상 / 잘못된 데이터 / 존재하지 않는 ID / 빈 데이터).

실행 전제: DB 가 떠 있고(docker compose up -d), 스키마가 적용되어 있을 것.
실행: cd backend && pytest -v
테스트용 종목(코드 999999)을 만들고, 끝나면 삭제한다. 기존 데이터는 건드리지 않는다.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
TEST_NAME = "테스트종목"


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


def price_body(company_id, date="2030-01-02", **override):
    body = {
        "company_id": company_id, "trade_date": date,
        "open_price": 100, "high_price": 120, "low_price": 90, "close_price": 110, "volume": 1000,
    }
    body.update(override)
    return body


# ---------- 상태 / 종목 ----------
def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_company_search(company):
    res = client.get("/companies", params={"q": TEST_NAME})
    assert res.status_code == 200
    assert [c["code"] for c in res.json()] == ["999999"]
    assert res.json()[0]["market_name"]


def test_company_update(company):
    res = client.put(f"/companies/{company['company_id']}", json={"name": TEST_NAME + "2"})
    assert res.status_code == 200 and res.json()["name"] == TEST_NAME + "2"
    client.put(f"/companies/{company['company_id']}", json={"name": TEST_NAME})


def test_company_duplicate_code(company):
    market_id = client.get("/markets").json()[0]["market_id"]
    res = client.post("/companies", json={"code": "999999", "name": "중복", "market_id": market_id})
    assert res.status_code == 409


def test_company_invalid_code():
    res = client.post("/companies", json={"code": "ABC", "name": "잘못", "market_id": 1})
    assert res.status_code == 422


def test_company_not_found():
    assert client.get("/companies/99999999").status_code == 404


# ---------- 시세 CRUD ----------
def test_price_crud(company):
    cid = company["company_id"]
    created = client.post("/prices", json=price_body(cid))
    assert created.status_code == 201, created.text
    pid = created.json()["price_id"]

    assert client.get(f"/prices/{pid}").json()["close_price"] == 110
    assert any(p["price_id"] == pid for p in client.get("/prices", params={"code": "999999"}).json())

    updated = client.put(f"/prices/{pid}", json={"close_price": 115})
    assert updated.status_code == 200 and updated.json()["close_price"] == 115

    assert client.delete(f"/prices/{pid}").status_code == 204
    assert client.get(f"/prices/{pid}").status_code == 404


def test_price_high_lower_than_low(company):
    res = client.post("/prices", json=price_body(company["company_id"], high_price=50, low_price=90))
    assert res.status_code == 422


def test_price_negative_volume(company):
    res = client.post("/prices", json=price_body(company["company_id"], volume=-1))
    assert res.status_code == 422


def test_price_duplicate_date(company):
    cid = company["company_id"]
    first = client.post("/prices", json=price_body(cid, date="2030-01-03"))
    assert first.status_code == 201
    assert client.post("/prices", json=price_body(cid, date="2030-01-03")).status_code == 409
    client.delete(f"/prices/{first.json()['price_id']}")


def test_price_unknown_company():
    assert client.post("/prices", json=price_body(99999999)).status_code == 404


def test_price_update_empty_body(company):
    created = client.post("/prices", json=price_body(company["company_id"], date="2030-01-04")).json()
    assert client.put(f"/prices/{created['price_id']}", json={}).status_code == 422
    client.delete(f"/prices/{created['price_id']}")


def test_price_update_breaks_high_low(company):
    created = client.post("/prices", json=price_body(company["company_id"], date="2030-01-07")).json()
    res = client.put(f"/prices/{created['price_id']}", json={"high_price": 10})
    assert res.status_code == 422
    client.delete(f"/prices/{created['price_id']}")


# ---------- 메모 CRUD ----------
def test_note_crud(company):
    cid = company["company_id"]
    created = client.post("/notes", json={"company_id": cid, "title": "관찰", "content": "거래량 증가"})
    assert created.status_code == 201
    nid = created.json()["note_id"]
    assert client.put(f"/notes/{nid}", json={"content": "수정됨"}).json()["content"] == "수정됨"
    assert client.get("/notes", params={"company_id": cid}).json()[0]["note_id"] == nid
    assert client.delete(f"/notes/{nid}").status_code == 204
    assert client.get(f"/notes/{nid}").status_code == 404


def test_note_empty_title(company):
    res = client.post("/notes", json={"company_id": company["company_id"], "title": "   ", "content": "x"})
    assert res.status_code == 422


# ---------- 통계 ----------
def test_statistics_summary(company):
    cid = company["company_id"]
    ids = [
        client.post("/prices", json=price_body(cid, date="2030-02-03", close_price=100)).json()["price_id"],
        client.post("/prices", json=price_body(cid, date="2030-02-04", close_price=200, high_price=250)).json()["price_id"],
    ]
    res = client.get("/statistics/summary", params={"code": "999999"})
    assert res.status_code == 200
    body = res.json()
    assert body["trading_days"] == 2 and body["min_close"] == 100 and body["max_close"] == 200
    assert body["avg_close"] == 150

    monthly = client.get("/statistics/monthly", params={"code": "999999", "year": 2030}).json()
    assert monthly[0]["month"] == "2030-02" and monthly[0]["trading_days"] == 2
    for pid in ids:
        client.delete(f"/prices/{pid}")


def test_statistics_unknown_code():
    assert client.get("/statistics/summary", params={"code": "000001"}).status_code == 404


def test_ranking_invalid_metric():
    assert client.get("/statistics/ranking", params={"metric": "per"}).status_code == 422


def test_ranking_and_sectors_respond():
    assert client.get("/statistics/ranking", params={"limit": 3}).status_code == 200
    assert client.get("/statistics/sectors").status_code == 200
    assert client.get("/statistics/volatile").status_code == 200
    assert client.get("/statistics/financial-ratios").status_code == 200
