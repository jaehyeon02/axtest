from collections import OrderedDict
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..analysis import build_analysis, collect_facts
from ..dashboard import build_dashboard, quick_insight, volatility
from ..database import get_db
from ..models import Candle, Consensus, Investor, News, Stock
from ..opinion import label_of, score_of, to_opinion
from ..schemas import (
    AnalysisOut, CandleOut, DashboardOut, InsightOut, InvestorOut, NewsOut, OpinionOut, RecommendedOut,
    StockDetail, StockOut,
)

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

# 정렬 기준 이름 → 정렬 컬럼
SORTS = {
    "value": desc(Stock.trade_value),  # 거래대금
    "volume": desc(Stock.volume),  # 거래량
    "rise": desc(Stock.change_rate),  # 급상승
    "fall": Stock.change_rate,  # 급하락
    "cap": desc(Stock.market_cap),  # 시가총액
}


def _get_stock(db: Session, code: str) -> Stock:
    stock = db.get(Stock, code)
    if not stock:
        raise HTTPException(404, "종목을 찾을 수 없어요.")
    return stock


@router.get("", response_model=List[StockOut])
def list_stocks(
    market: str = Query("all", pattern="^(all|kr|us)$"),
    sort: str = Query("value", pattern="^(value|volume|rise|fall|cap)$"),
    q: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """종목 순위 목록. 시장(전체/국내/해외)과 정렬 기준, 검색어(q)를 지원합니다."""
    query = db.query(Stock)
    if market != "all":
        query = query.filter(Stock.market == market)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((Stock.name.ilike(like)) | (Stock.code.ilike(like)))
    return query.order_by(SORTS[sort]).limit(limit).all()


# 아래 경로들은 "/{code}" 보다 먼저 선언해야 "recommended"가 종목코드로 오해되지 않아요.
@router.get("/recommended", response_model=List[RecommendedOut])
def recommended(
    market: str = Query("all", pattern="^(all|kr|us)$"),
    limit: int = Query(6, ge=1, le=20),
    style: str = Query("normal", pattern="^(safe|normal|bold)$"),
    db: Session = Depends(get_db),
):
    """추천 종목: 전문가 투자의견 점수가 높은 순서.

    style(투자성향): safe=가격이 덜 출렁이는 종목, bold=많이 출렁이는 종목 중에서 고르고, normal=전체.
    """
    query = db.query(Stock, Consensus).join(Consensus, Consensus.code == Stock.code)
    if market != "all":
        query = query.filter(Stock.market == market)
    rows = []
    for stock, c in query.all():
        score = score_of(c)
        total = c.strong_buy + c.buy + c.hold + c.sell + c.strong_sell
        rows.append((score, total, stock, volatility(db, stock.code)))
    if style != "normal" and rows:
        mid = sorted(r[3] for r in rows)[len(rows) // 2]  # 변동성 중앙값을 기준으로 절반씩 나눠요
        rows = [r for r in rows if (r[3] <= mid if style == "safe" else r[3] >= mid)]
    rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
    return [
        RecommendedOut(**StockOut.model_validate(st).model_dump(), score=sc, label=label_of(sc), total=tt, volatility=vol)
        for sc, tt, st, vol in rows[:limit]
    ]


@router.get("/insights", response_model=Dict[str, InsightOut])
def insights(
    codes: str = Query(..., max_length=600, description="쉼표로 구분한 종목코드"),
    db: Session = Depends(get_db),
):
    """홈 카드용 요약: 1년 가격 위치, 1주·1개월·3개월 수익률, 전문가 의견 라벨."""
    out = {}
    for code in [c for c in codes.split(",") if c][:30]:
        info = quick_insight(db, code)
        if info:
            out[code] = info
    return out


@router.get("/{code}", response_model=StockDetail)
def stock_detail(code: str, db: Session = Depends(get_db)):
    stock = _get_stock(db, code)
    facts = collect_facts(db, stock)
    today = (
        db.query(Candle).filter(Candle.code == code).order_by(desc(Candle.day)).first()
    )
    return StockDetail(
        **StockOut.model_validate(stock).model_dump(),
        day_low=today.low, day_high=today.high,
        week52_low=facts["week52_low"], week52_high=facts["week52_high"],
        value_rank=facts["rank"],
    )


@router.get("/{code}/candles", response_model=List[CandleOut])
def candles(
    code: str,
    interval: str = Query("D", pattern="^(D|W|M)$"),
    limit: int = Query(600, le=2000),
    db: Session = Depends(get_db),
):
    """일(D)·주(W)·월(M)봉. 일봉을 DB에 저장하고 주·월봉은 여기서 묶어서 만듭니다."""
    _get_stock(db, code)
    rows = db.query(Candle).filter(Candle.code == code).order_by(Candle.day).all()

    if interval == "D":
        merged = [(r.day, r.open, r.high, r.low, r.close, r.volume) for r in rows]
    else:
        buckets: "OrderedDict[tuple, list]" = OrderedDict()
        for r in rows:
            key = tuple(r.day.isocalendar()[:2]) if interval == "W" else (r.day.year, r.day.month)
            if key not in buckets:
                buckets[key] = [r.day, r.open, r.high, r.low, r.close, r.volume]
            else:
                b = buckets[key]
                b[2], b[3] = max(b[2], r.high), min(b[3], r.low)
                b[4] = r.close
                b[5] += r.volume
        merged = [tuple(b) for b in buckets.values()]

    return [CandleOut(t=t, o=o, h=h, l=l, c=c, v=v) for (t, o, h, l, c, v) in merged[-limit:]]


@router.get("/{code}/analysis", response_model=AnalysisOut)
def analysis(code: str, db: Session = Depends(get_db)):
    return build_analysis(db, _get_stock(db, code))


@router.get("/{code}/news", response_model=List[NewsOut])
def news(code: str, db: Session = Depends(get_db)):
    _get_stock(db, code)
    return db.query(News).filter(News.code == code).order_by(desc(News.published_at)).all()


@router.get("/{code}/investors", response_model=List[InvestorOut])
def investors(code: str, db: Session = Depends(get_db)):
    """최근 거래일부터 개인·외국인·기관 순매수."""
    _get_stock(db, code)
    return db.query(Investor).filter(Investor.code == code).order_by(desc(Investor.day)).all()


@router.get("/{code}/opinion", response_model=OpinionOut)
def opinion(code: str, db: Session = Depends(get_db)):
    """전문가 투자의견: 적극매수·매수·중립·매도·적극매도 의견 수와 목표주가."""
    stock = _get_stock(db, code)
    c = db.get(Consensus, code)
    if not c:
        raise HTTPException(404, "투자의견 데이터가 없어요.")
    return to_opinion(stock, c)


@router.get("/{code}/dashboard", response_model=DashboardOut)
def dashboard(code: str, db: Session = Depends(get_db)):
    """종목 상세 '한눈에 보기' 화면에 필요한 값을 한 번에 돌려줍니다."""
    return build_dashboard(db, _get_stock(db, code))
