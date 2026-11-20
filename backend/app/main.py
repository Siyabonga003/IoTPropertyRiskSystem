from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import alerts as alerts_api
from app.api import devices as devices_api
from app.api import events as events_api
from app.api import ingest as ingest_api
from app.api import pairing as pairing_api
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


app = FastAPI(title="IoT Property Risk Monitoring API", version="0.1.0", lifespan=lifespan)
app.include_router(devices_api.router)
app.include_router(ingest_api.router)
app.include_router(alerts_api.router)
app.include_router(users_api.router)
app.include_router(pairing_api.router)
app.include_router(events_api.router)
