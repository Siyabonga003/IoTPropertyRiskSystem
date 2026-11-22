from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import alerts as alerts_api
from app.api import devices as devices_api
from app.api import events as events_api
from app.api import ingest as ingest_api
from app.api import pairing as pairing_api
from app.api import system as system_api
from app.api import users as users_api
from app.config import config
from app.database import SessionLocal, init_db
from app.risk import check_stale_devices


async def _sweep_loop() -> None:
    while True:
        await asyncio.sleep(config.SWEEP_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            check_stale_devices(db)
        except Exception:  # keep the sweeper alive; failures are logged below
            logging.getLogger(__name__).exception("sweep iteration failed")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(_sweep_loop())
    try:
        yield
    finally:
        task.cancel()


_ERROR_CODES = {
    400: "INVALID",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "INVALID",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL",
}
_UPPER_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _error_body(status_code: int, detail) -> dict:
    """Normalize errors to the SPEC §4 envelope: {error: {code, message}}."""
    message = detail if isinstance(detail, str) else str(detail)
    code = message if _UPPER_CODE_RE.fullmatch(message or "") else _ERROR_CODES.get(status_code, "ERROR")
    return {"error": {"code": code, "message": message}}


app = FastAPI(title="IoT Property Risk Monitoring API", version="0.1.0", lifespan=lifespan)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=_error_body(exc.status_code, exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "INVALID", "message": "request validation failed", "details": jsonable_encoder(exc.errors())}},
    )


app.include_router(devices_api.router)
app.include_router(ingest_api.router)
app.include_router(alerts_api.router)
app.include_router(users_api.router)
app.include_router(pairing_api.router)
app.include_router(events_api.router)
app.include_router(system_api.router)
