import logging, time
from collections import defaultdict, deque
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from app.core.config import settings as app_settings
from .core.db import Base, engine
from .core.logging import setup_logging
from .api import auth, shipments, ops

setup_logging()
log = logging.getLogger("app")
Base.metadata.create_all(engine)   # use Alembic migrations in production

app = FastAPI(title="Logistics Platform", version="1.0")
app.include_router(auth.router)
app.include_router(shipments.router)
app.include_router(ops.router)

_hits: dict[str, deque] = defaultdict(deque)


class Settings:
    """Compatibility wrapper around the app settings object."""

    @property
    def RATE_LIMIT_PER_MIN(self):
        return app_settings.RATE_LIMIT_PER_MIN


settings = Settings()


@app.middleware("http")
async def rate_limit_and_log(request: Request, call_next):
    ip = request.client.host if request.client else "?"
    now = time.time(); q = _hits[ip]
    while q and q[0] < now - 60:
        q.popleft()
    if len(q) >= settings.RATE_LIMIT_PER_MIN:
        return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
    q.append(now)
    resp = await call_next(request)
    log.info("request", extra={"extra_data": {"path": request.url.path,
             "status": resp.status_code, "ms": round((time.time() - now) * 1000)}})
    return resp


@app.exception_handler(OperationalError)
async def db_down(request: Request, exc: OperationalError):
    log.error("database failure")
    return JSONResponse({"detail": "Service temporarily unavailable"}, status_code=503)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error")
    return JSONResponse({"detail": "Internal server error"}, status_code=500)
