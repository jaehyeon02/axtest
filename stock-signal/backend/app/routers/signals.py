"""신호등·지표 API. 계산은 DB 뷰가 하고, 여기서는 SQL 을 실행해 결과를 돌려 준다."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import queries
from app.db import get_db

router = APIRouter(prefix="/signals", tags=["신호등·지표"])


def _rows(db: Session, sql: str, **params) -> list[dict]:
    return [dict(r) for r in db.execute(text(sql), params).mappings().all()]


# ORDER BY 는 바인딩 파라미터로 줄 수 없으므로 허용 목록으로만 SQL 을 조립한다.
ORDER_COLS = {"good": "good_cnt", "caution": "caution_cnt", "change": "v.change_pct", "ret_1m": "v.ret_1m", "code": "c.code"}
RET_COLS = {"1w": "ret_1w", "1m": "ret_1m", "3m": "ret_3m"}


@router.get("", summary="전체 종목 신호등 목록 (시세 없는 종목은 지표가 비어 있음)")
def list_signals(
    sector: str | None = Query(None, description="업종 이름 (예: 반도체)"),
    market: str | None = Query(None, description="KOSPI / KOSDAQ"),
    order_by: Literal["good", "caution", "change", "ret_1m", "code"] = "good",
    db: Session = Depends(get_db),
):
    direction = "ASC" if order_by == "code" else "DESC"
    sql = queries.SIGNALS.format(order_col=ORDER_COLS[order_by], direction=direction)
    return _rows(db, sql, sector=sector, market=market)


@router.get("/returns", summary="기간 수익률 순위 (1주 / 1개월 / 3개월)")
def returns(
    period: Literal["1w", "1m", "3m"] = "1m",
    order: Literal["desc", "asc"] = "desc",
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    sql = queries.RETURNS.format(ret_col=RET_COLS[period], direction="DESC" if order == "desc" else "ASC")
    return _rows(db, sql, limit=limit)


@router.get("/sectors", summary="업종 요약 (평균 1개월 수익률, 추세가 좋은 종목 수)")
def by_sector(min_companies: int = Query(1, ge=1, le=100), db: Session = Depends(get_db)):
    return _rows(db, queries.SECTORS, min_companies=min_companies)


@router.get("/compare", summary="종목 비교 (쉼표로 구분한 종목코드 2~5개)")
def compare(codes: str = Query(..., description="예: 005930,000660"), db: Session = Depends(get_db)):
    items = [c.strip() for c in codes.split(",") if c.strip()]
    if not 2 <= len(items) <= 5:
        raise HTTPException(422, "비교할 종목코드를 2~5개 보내세요.")
    if any(len(c) != 6 or not c.isalnum() for c in items):
        raise HTTPException(422, "종목코드는 영문 대문자·숫자 6자리입니다.")
    return _rows(db, queries.COMPARE, codes="{" + ",".join(items) + "}")


@router.get("/{code}", summary="종목 1개의 신호등과 지표")
def signal_one(code: str, db: Session = Depends(get_db)):
    rows = _rows(db, queries.SIGNAL_ONE, code=code)
    if not rows:
        raise HTTPException(404, "존재하지 않는 종목입니다.")
    return rows[0]


@router.get("/{code}/series", summary="차트용 시계열 (종가 + 5/20/60일 이동평균)")
def series(code: str, limit: int = Query(120, ge=1, le=1000), db: Session = Depends(get_db)):
    rows = _rows(db, queries.SERIES, code=code, limit=limit)
    if not rows:
        raise HTTPException(404, "해당 종목의 시세 데이터가 없습니다.")
    return rows
