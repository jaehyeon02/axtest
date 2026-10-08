from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import events as ev
from ..deps import company_or_404, get_repo
from ..repo import Repo
from ..schemas import AnalysisOut, CompanyOut, DocumentOut, EventOut, FinancialOut, MonthlyOut, PeerOut, PriceOut

router = APIRouter(prefix="/api/companies", tags=["companies"])


def _doc(d: dict) -> dict:
    return {**{k: d[k] for k in ("doc_id", "company_id", "doc_type", "title", "body", "source", "sentiment", "published_date", "rcept_no", "url")},
            "user_added": d["created_by"] is not None}


@router.get("", response_model=List[CompanyOut])
def list_companies(q: str = Query("", max_length=40), repo: Repo = Depends(get_repo)):
    """종목 목록·검색(이름 또는 코드)."""
    return repo.companies(q)


@router.get("/{code}", response_model=CompanyOut)
def company_detail(code: str, repo: Repo = Depends(get_repo)):
    c = company_or_404(repo, code)
    return next(x for x in repo.companies("") if x["code"] == c["code"])


@router.get("/{code}/prices", response_model=List[PriceOut])
def prices(code: str, days: int = Query(250, ge=5, le=365), repo: Repo = Depends(get_repo)):
    c = company_or_404(repo, code)
    last = repo.latest_date(c["company_id"])
    return repo.series(c["company_id"], last - timedelta(days=days)) if last else []


@router.get("/{code}/events", response_model=List[EventOut])
def events(code: str, days: int = Query(365, ge=5, le=365), threshold: float = Query(ev.MOVE_THRESHOLD, ge=1, le=20), repo: Repo = Depends(get_repo)):
    """주가가 크게 움직인 날과, 그날 전후에 나온 공시·내 자료."""
    c = company_or_404(repo, code)
    cid = c["company_id"]
    today = repo.latest_date(cid)
    if today is None:  # 아직 시세를 수집하지 않은 종목
        return []
    movers = repo.movers(cid, today - timedelta(days=days), threshold)
    docs = repo.documents(cid, today - timedelta(days=days + 5))
    linked = ev.link_movers(movers, docs, limit=3)
    return [{**item["mover"], "docs": [_doc(d) for d in item["docs"]]} for item in linked]


@router.get("/{code}/monthly", response_model=List[MonthlyOut])
def monthly(code: str, repo: Repo = Depends(get_repo)):
    return repo.monthly(company_or_404(repo, code)["company_id"])


@router.get("/{code}/financials", response_model=List[FinancialOut])
def financials(code: str, repo: Repo = Depends(get_repo)):
    """연간 재무(최근 5개년) + 영업이익률 + 전년 대비 매출 성장률."""
    return repo.financials(company_or_404(repo, code)["company_id"], 5)


@router.get("/{code}/analysis", response_model=AnalysisOut)
def analysis(code: str, repo: Repo = Depends(get_repo)):
    """가격 흐름 숫자: 1·3·6개월 수익률, 최대 낙폭(1년), 변동성, 120일선 괴리율."""
    out = repo.analysis(company_or_404(repo, code)["company_id"])
    if out is None:
        raise HTTPException(404, "시세 데이터가 없어요.")
    return out


@router.get("/{code}/peers", response_model=List[PeerOut])
def peers(code: str, repo: Repo = Depends(get_repo)):
    """같은 업종 회사들과 최신 연도 영업이익률·매출 성장률 비교(순위·평균 포함)."""
    return repo.peers(company_or_404(repo, code)["company_id"])


@router.get("/{code}/documents", response_model=List[DocumentOut])
def documents(code: str, doc_type: str = Query("", pattern="^(|news|filing)$"), days: int = Query(365, ge=1, le=365), repo: Repo = Depends(get_repo)):
    c = company_or_404(repo, code)
    since = repo.latest_date(c["company_id"]) - timedelta(days=days)
    rows = repo.documents(c["company_id"], since)
    return [_doc(d) for d in rows if not doc_type or d["doc_type"] == doc_type]
