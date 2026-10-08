from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import register_handlers, setup_logging
from app.routers import companies, members, prices, signals, trades, watchlist

setup_logging()

app = FastAPI(
    title="종목 신호등 서비스",
    description="주가를 PostgreSQL 에 구축하고, 이동평균·52주 위치·신호등을 SQL 뷰로 계산해 "
    "관심종목·모의 거래와 함께 제공하는 1차 세미프로젝트 API",
    version="0.1.0",
)
register_handlers(app)

for r in (companies.router, prices.router, members.router, watchlist.router, trades.router, signals.router):
    app.include_router(r)


@app.get("/health", tags=["상태"], summary="서버/DB 연결 확인")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


# 대시보드 화면(선택 사항): app/static 의 HTML/JS 를 그대로 내려 준다 (같은 서버라 CORS 불필요)
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/dashboard", StaticFiles(directory=STATIC_DIR, html=True), name="dashboard")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/dashboard/")
