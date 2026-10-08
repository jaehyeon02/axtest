"""API 테스트: pip install pytest httpx 후  pytest backend/tests/test_api.py
임시 SQLite 파일을 쓰도록 DATABASE_URL 을 먼저 정해요."""
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


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # with 문이 lifespan(테이블 생성+샘플 데이터)을 실행해요
        yield c


def test_companies_and_search(client):
    assert len(client.get("/api/companies").json()) == 8
    found = client.get("/api/companies", params={"q": "하이닉스"}).json()
    assert [c["code"] for c in found] == ["000660"]
    assert client.get("/api/companies/999999").status_code == 404


def test_events_link_filings(client):
    events = client.get("/api/companies/005930/events").json()
    assert events and all(e["docs"] for e in events)


def test_analysis_peers_financials(client):
    a = client.get("/api/companies/005930/analysis").json()
    assert set(a["returns"]) == {"1개월", "3개월", "6개월"} and a["mdd"] <= 0 and a["volatility_annual"] > 0
    peers = client.get("/api/companies/005930/peers").json()
    assert {p["code"] for p in peers} == {"005930", "000660"} and peers[0]["margin_rank"] == 1
    fins = client.get("/api/companies/005930/financials").json()
    assert len(fins) == 5 and fins[0]["fiscal_year"] > fins[-1]["fiscal_year"] and fins[-1]["rev_growth"] is None


def test_watchlist_crud_and_privacy(client):
    assert client.get("/api/watchlist", headers=A).json() == []
    assert client.get("/api/watchlist").status_code == 400  # X-Client-Id 가 없으면 거절
    w = client.put("/api/watchlist/005930", headers=A).json()
    assert [x["company"]["code"] for x in w] == ["005930"] and w[0]["company"]["price"] > 0
    assert len(client.put("/api/watchlist/005930", headers=A).json()) == 1  # 두 번 담아도 하나(UNIQUE)
    assert len(client.put("/api/watchlist/000660", headers=A).json()) == 2
    assert client.get("/api/watchlist", headers=B).json() == []  # 남의 관심종목은 안 보여요
    assert client.put("/api/watchlist/999999", headers=A).status_code == 404
    assert [x["company"]["code"] for x in client.delete("/api/watchlist/005930", headers=A).json()] == ["000660"]
    assert client.delete("/api/watchlist/005930", headers=A).status_code == 404


def test_status_says_sample(client):
    s = client.get("/api/status").json()
    assert s["is_sample"] is True and s["source"] == "sample" and s["counts"]["company"] == 8


def test_note_crud_and_privacy(client):
    n = client.post("/api/notes", json={"company_code": "005930", "title": "HBM 관찰", "memo": "메모", "stance": "pos"}, headers=A)
    assert n.status_code == 201
    nid = n.json()["note_id"]
    assert client.get(f"/api/notes/{nid}", headers=B).status_code == 404  # 남의 노트는 안 보여요
    upd = client.put(f"/api/notes/{nid}", json={"title": "HBM 관찰 v2"}, headers=A).json()
    assert upd["title"] == "HBM 관찰 v2" and upd["memo"] == "메모"

    doc_id = client.get("/api/companies/005930/documents").json()[0]["doc_id"]
    price_id = client.get("/api/companies/005930/events").json()[0]["price_id"]
    assert client.post(f"/api/notes/{nid}/evidence", json={"doc_id": doc_id, "price_id": price_id}, headers=A).status_code == 422
    with_doc = client.post(f"/api/notes/{nid}/evidence", json={"doc_id": doc_id, "comment": "근거1"}, headers=A).json()
    assert with_doc["evidence"][0]["kind"] == "document"
    assert client.post(f"/api/notes/{nid}/evidence", json={"doc_id": doc_id}, headers=A).status_code == 409
    with_price = client.post(f"/api/notes/{nid}/evidence", json={"price_id": price_id}, headers=A).json()
    assert [e["kind"] for e in with_price["evidence"]] == ["document", "price"]
    other_company_doc = client.get("/api/companies/000660/documents").json()[0]["doc_id"]
    assert client.post(f"/api/notes/{nid}/evidence", json={"doc_id": other_company_doc}, headers=A).status_code == 404

    eid = with_price["evidence"][0]["evidence_id"]
    edited = client.put(f"/api/notes/{nid}/evidence/{eid}", json={"comment": "내 코멘트"}, headers=A).json()
    assert edited["evidence"][0]["comment"] == "내 코멘트"
    assert len(client.delete(f"/api/notes/{nid}/evidence/{eid}", headers=A).json()["evidence"]) == 1
    assert client.delete(f"/api/notes/{nid}", headers=A).status_code == 204
    assert client.get(f"/api/notes/{nid}", headers=A).status_code == 404


def test_user_documents(client):
    body = {"company_code": "005930", "title": "직접 찾은 기사", "body": "본문 내용", "published_date": "2026-10-01", "sentiment": "pos", "url": "https://example.com/a"}
    assert client.post("/api/documents", json={**body, "url": "javascript:alert(1)"}, headers=A).status_code == 422  # 링크는 http(s)만
    d = client.post("/api/documents", json=body, headers=A)
    assert d.status_code == 201 and d.json()["user_added"] is True and d.json()["doc_type"] == "news"
    did = d.json()["doc_id"]
    assert client.put(f"/api/documents/{did}", json={"title": "수정"}, headers=B).status_code == 403
    assert client.put(f"/api/documents/{did}", json={"title": "수정"}, headers=A).json()["title"] == "수정"
    assert any(x["doc_id"] == did for x in client.get("/api/companies/005930/documents", headers=A).json())
    assert not any(x["doc_id"] == did for x in client.get("/api/companies/005930/documents", headers=B).json())  # 내 자료는 남에게 안 보여요
    assert client.delete("/api/documents/1", headers=A).status_code == 403  # 수집 문서는 삭제 불가
    assert client.delete(f"/api/documents/{did}", headers=A).status_code == 204


def test_web_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "AX" in r.text
    assert client.get("/app.js").status_code == 200
