from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401  (테이블 등록)
from .database import Base, SessionLocal, engine
from .routers import market, stocks, watchlist
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버가 켜질 때: 테이블 생성 → 비어 있으면 샘플 데이터 입력
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="AX 증권 API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router)
app.include_router(stocks.router)
app.include_router(watchlist.router)


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}
