"""로깅 설정과 공통 예외 처리.

DB 제약조건(UNIQUE, FK, CHECK ...)에 걸리면 PostgreSQL 이 오류 코드(pgcode)를 돌려준다.
이를 사용자가 이해할 수 있는 HTTP 상태코드/메시지로 바꿔 준다.
"""
import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

logger = logging.getLogger("stockdb")

PG_ERRORS = {
    "23505": (409, "이미 존재하는 데이터입니다."),  # unique_violation
    "23503": (409, "존재하지 않는 데이터를 참조했거나, 다른 데이터가 참조 중이라 처리할 수 없습니다."),  # foreign_key_violation
    "23514": (422, "허용되지 않는 값입니다. (제약 조건 위반)"),  # check_violation
    "23502": (422, "필수 값이 비어 있습니다."),  # not_null_violation
}


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def register_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def access_log(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        logger.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, ms)
        return response

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        pgcode = getattr(exc.orig, "pgcode", None)
        status, message = PG_ERRORS.get(pgcode, (400, "데이터 처리 중 오류가 발생했습니다."))
        logger.warning("IntegrityError pgcode=%s path=%s detail=%s", pgcode, request.url.path, exc.orig)
        return JSONResponse(status_code=status, content={"detail": message})

    @app.exception_handler(SQLAlchemyError)
    async def db_error_handler(request: Request, exc: SQLAlchemyError):
        logger.exception("DB error path=%s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "데이터베이스 오류가 발생했습니다."})
