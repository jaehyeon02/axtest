import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from pathlib import Path

from . import models  # noqa: F401  (테이블 등록)
from .database import Base, SessionLocal, engine
from .routers import companies, documents, notes, system, watchlist
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버가 켜질 때: 테이블 생성 → 비어 있으면 샘플 데이터 입력
    Base.metadata.create_all(engine)
    if os.getenv("SEED_SAMPLE", "1") != "0":  # 실데이터를 쓸 거면 SEED_SAMPLE=0
        with SessionLocal() as db:
            seed(db)
    yield


app = FastAPI(title="AX 근거노트 API", version="2.0.0", lifespan=lifespan)

for r in (companies.router, documents.router, notes.router, watchlist.router, system.router):
    app.include_router(r)


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}


# 화면(HTML/CSS/JS)은 프레임워크 없이 정적 파일로 서버가 그대로 내려줘요. API 경로(/api)가 먼저 처리돼요.
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="web")
