"""SQL 기반 통계 API. (AI 가 아니라 JOIN / GROUP BY / HAVING 으로 만드는 '인사이트')"""
import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import queries
from app.db import get_db

router = APIRouter(prefix="/statistics", tags=["통계"])


def _rows(db: Session, sql: str, **params) -> list[dict]:
    return [dict(r) for r in db.execute(text(sql), params).mappings().all()]


@router.get("/summary", summary="종목 요약 (거래일수, 평균/최고/최저 종가, 평균 거래량)")
def summary(
    code: str,
    start: dt.date | None = None,
    end: dt.date | None = None,
    db: Session = Depends(get_db),
):
    rows = _rows(db, queries.SUMMARY, code=code, start=start, end=end)
    if not rows:
        raise HTTPException(404, "해당 종목의 시세 데이터가 없습니다.")
    return rows[0]


@router.get("/monthly", summary="월별 통계 (평균 종가, 최고/최저가, 거래량 합계)")
def monthly(code: str, year: int | None = Query(None, ge=1990, le=2100), db: Session = Depends(get_db)):
    rows = _rows(db, queries.MONTHLY, code=code, year=year)
    if not rows:
        raise HTTPException(404, "해당 조건의 시세 데이터가 없습니다.")
    return rows


@router.get("/sectors", summary="업종별 평균 등락률 (최근 N일)")
def by_sector(days: int = Query(30, ge=1, le=3650), db: Session = Depends(get_db)):
    return _rows(db, queries.SECTORS, days=days)


@router.get("/ranking", summary="특정 일자 TOP N (등락률 또는 거래량)")
def ranking(
    metric: Literal["change", "volume"] = "change",
    order: Literal["desc", "asc"] = "desc",
    day: dt.date | None = Query(None, description="비우면 가장 최근 거래일"),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    # ORDER BY 는 바인딩 파라미터로 줄 수 없으므로 허용 목록으로만 SQL 을 조립한다.
    order_col = {"change": "v.change_pct", "volume": "v.volume"}[metric]
    direction = "DESC" if order == "desc" else "ASC"
    sql = queries.RANKING.format(order_col=order_col, direction=direction)
    return _rows(db, sql, day=day, metric=metric, limit=limit)


@router.get("/volatile", summary="변동성 큰 종목 (±threshold% 이상 움직인 날이 min_days일 이상)")
def volatile(
    threshold: float = Query(4.0, gt=0, le=30),
    days: int = Query(180, ge=1, le=3650),
    min_days: int = Query(3, ge=1),
    db: Session = Depends(get_db),
):
    return _rows(db, queries.VOLATILE, threshold=threshold, days=days, min_days=min_days)


@router.get("/financial-ratios", summary="재무 비율 (영업이익률, 부채비율, ROE)")
def financial_ratios(code: str | None = None, db: Session = Depends(get_db)):
    return _rows(db, queries.FINANCIAL_RATIOS, code=code)
