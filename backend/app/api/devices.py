from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.serializers import serialize_device, serialize_event
from app.database import get_db
from app.models import (
    Alert,
    Device,
    DeviceToken,
    Property,
    TelemetryEvent,
    current_system_mode,
    utcnow,
)
from app.risk import recompute_property_risk
from app.security import (
    get_current_device,
    get_current_user,
    require_role,
    user_property_ids,
)

router = APIRouter()


def get_device_or_404(db, user_id: str, device_id: str) -> Device:
    device = db.query(Device).filter_by(device_id=device_id).one_or_none()
    if device is None or device.property_id not in user_property_ids(db, user_id):
        raise HTTPException(status_code=404, detail="Not found")
    return device


@router.get("/api/v1/devices")
def list_devices(db=Depends(get_db), user=Depends(get_current_user)):
    props = user_property_ids(db, user.id)
    if not props:
        return []
    devices = db.query(Device).filter(Device.property_id.in_(props)).order_by(Device.device_id).all()
    return [serialize_device(d, current_system_mode(db, d.property_id)) for d in devices]


@router.get("/api/v1/devices/{device_id}")
def get_device(device_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    device = get_device_or_404(db, user.id, device_id)
    return serialize_device(device, current_system_mode(db, device.property_id))


@router.get("/api/v1/devices/{device_id}/status")
def get_device_status(device_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    device = get_device_or_404(db, user.id, device_id)
    prop = db.get(Property, device.property_id) if device.property_id else None
    last = (
        db.query(TelemetryEvent)
        .filter_by(device_id=device.device_id)
        .order_by(TelemetryEvent.sequence.desc())
        .first()
    )
    return {
        "device": serialize_device(device, current_system_mode(db, device.property_id)),
        "property_risk_level": prop.risk_level if prop else 0,
        "last_telemetry": serialize_event(last) if last else None,
    }


@router.get("/api/v1/devices/{device_id}/events")
def get_device_events(
    device_id: str,
    request: Request,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    get_device_or_404(db, user.id, device_id)
    try:
        cursor = int(request.query_params.get("cursor", "0") or 0)
    except ValueError:
        cursor = 0
    events = (
        db.query(TelemetryEvent)
        .filter_by(device_id=device_id)
        .filter(TelemetryEvent.sequence > cursor)
        .order_by(TelemetryEvent.sequence.asc())
        .limit(100)
        .all()
    )
    return {"events": [serialize_event(e) for e in events]}


@router.delete("/api/v1/devices/{device_id}")
def revoke_device(device_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    device = get_device_or_404(db, user.id, device_id)
    require_role(db, user.id, device.property_id, {"owner", "admin"})
    now = utcnow()
    device.status = "revoked"
    token = db.query(DeviceToken).filter_by(device_id=device.device_id).one_or_none()
    if token is not None:
        token.revoked_at = now
    # A revoked device will never report recovery, so close its open alerts.
    for alert in db.query(Alert).filter_by(device_id=device.device_id, status="open").all():
        alert.status = "resolved"
        alert.resolved_at = now
    recompute_property_risk(db, device.property_id)
    db.commit()
    return serialize_device(device, current_system_mode(db, device.property_id))


@router.get("/api/v1/devices/{device_id}/mode")
def get_device_mode(device_id: str, db=Depends(get_db), device: Device = Depends(get_current_device)):
    """Current system mode for the device's property (device-token auth, SPEC §4)."""
    if device.device_id != device_id:
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")
    return {"mode": current_system_mode(db, device.property_id)}
