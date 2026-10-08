from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import register_handlers, setup_logging
from app.routers import companies, financials, notes, prices, statistics

setup_logging()

app = FastAPI(
    title="주식 종목 데이터 서비스",
    description="주가·재무 데이터를 PostgreSQL 에 구축하고, CRUD 와 SQL 통계를 제공하는 1차 세미프로젝트 API",
    version="0.1.0",
)
register_handlers(app)

for r in (companies.router, prices.router, financials.router, notes.router, statistics.router):
    app.include_router(r)


@app.get("/health", tags=["상태"], summary="서버/DB 연결 확인")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


# 대시보드 화면: app/static 의 HTML/JS 를 그대로 내려 준다 (같은 서버라서 CORS 설정이 필요 없다)
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/dashboard", StaticFiles(directory=STATIC_DIR, html=True), name="dashboard")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/dashboard/")
