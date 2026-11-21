from __future__ import annotations

import asyncio

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)

from app.api.serializers import serialize_alert, serialize_event
from app.database import get_db
from app.models import Alert, Device, TelemetryEvent, User
from app.security import decode_user_token, user_property_ids

router = APIRouter()


def _token_from_scope(scope) -> str:
    token = scope.query_params.get("token") or ""
    if not token:
        auth = scope.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    return token


def _get_device_or_404(db, user: User, device_id: str) -> Device:
    device = db.query(Device).filter_by(device_id=device_id).one_or_none()
    if device is None or device.property_id not in user_property_ids(db, user.id):
        raise HTTPException(status_code=404, detail="Not found")
    return device


# NOTE: the HTTP route `GET /api/v1/devices/{device_id}/events` lives in
# app/api/devices.py (registered first in app/main.py); the same path is not
# duplicated here, which would shadow it. Only the WebSocket stream is
# registered by this router.


@router.websocket("/api/v1/devices/{device_id}/stream")
async def device_stream(websocket: WebSocket, device_id: str, db=Depends(get_db)):
    claims = decode_user_token(_token_from_scope(websocket))
    if claims is None:
        await websocket.close(code=1008)
        return
    user = db.get(User, claims["sub"])
    if user is None or _get_device_or_404(db, user, device_id) is None:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    await websocket.send_json({"type": "connected", "device_id": device_id, "sequence": 0})
    last_sequence = 0
    sent_alerts: set[str] = set()
    try:
        while True:
            events = (
                db.query(TelemetryEvent)
                .filter_by(device_id=device_id)
                .filter(TelemetryEvent.sequence > last_sequence)
                .order_by(TelemetryEvent.sequence.asc())
                .all()
            )
            for event in events:
                last_sequence = max(last_sequence, event.sequence)
                await websocket.send_json({"type": "telemetry", "payload": serialize_event(event)})
            for alert in db.query(Alert).filter_by(device_id=device_id, status="open").all():
                if alert.id not in sent_alerts:
                    sent_alerts.add(alert.id)
                    await websocket.send_json({"type": "alert", "payload": serialize_alert(alert)})
            await asyncio.sleep(0.5)
    except (WebSocketDisconnect, RuntimeError):
        return
