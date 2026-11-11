import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError

log = logging.getLogger("app.errors")


from app.core.errors import (AppError, ConflictError, ForbiddenError, InvalidTransitionError,  # noqa: F401
                             NotFoundError)


def _body(code: str, message: str, request: Request) -> dict:
    return {"error": {"code": code, "message": message, "request_id": getattr(request.state, "request_id", None)}}


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message, request))

    @app.exception_handler(OperationalError)
    async def db_down(request: Request, exc: OperationalError):
        log.error("database unavailable", exc_info=exc)
        return JSONResponse(status_code=503, content=_body("db_unavailable", "Service temporarily unavailable", request))

    @app.exception_handler(SQLAlchemyError)
    async def db_error(request: Request, exc: SQLAlchemyError):
        log.error("database error", exc_info=exc)
        return JSONResponse(status_code=500, content=_body("db_error", "Internal error", request))
