from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from app.alerts import apply_transitions, dispatch_new_alerts
from app.database import get_db
from app.models import Alert, Device, TelemetryEvent, utcnow
from app.risk import recompute_property_risk
from app.security import get_current_device
from app.thresholds import compute_levels, device_risk_level

router = APIRouter()


def _num(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _int(value) -> int | None:
    v = _num(value)
    return int(v) if v is not None else None


def _parse_ts(value) -> datetime | None:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    return None


@router.post("/api/v1/ingest/telemetry")
async def ingest_telemetry(
    request: Request,
    db=Depends(get_db),
    device: Device = Depends(get_current_device),
):
    if device.status != "active" or not device.property_id:
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")
    data = await request.json()
    sequence = data.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence <= 0:
        raise HTTPException(status_code=422, detail="sequence must be a positive integer")
    existing = (
        db.query(TelemetryEvent)
        .filter_by(device_id=device.device_id, sequence=sequence)
        .one_or_none()
    )
    if existing is not None:
        return {"accepted": False, "reason": "stale_sequence", "sequence": sequence}

    now = utcnow()
    smoke_ppm = _num(data.get("smoke_ppm"))
    gas_ppm = _num(data.get("gas_ppm"))
    flame_detected = bool(data.get("flame_detected"))
    water_level = _int(data.get("water_level"))
    motion_detected = bool(data.get("motion_detected"))
    faults = [f for f in (data.get("faults") or []) if isinstance(f, str)]
    event = TelemetryEvent(
        device_id=device.device_id,
        property_id=device.property_id,
        sequence=sequence,
        timestamp=_parse_ts(data.get("timestamp")) or now,
        received_at=now,
        smoke_ppm=smoke_ppm,
        gas_ppm=gas_ppm,
        flame_detected=flame_detected,
        water_level=water_level if water_level is not None else 0,
        motion_detected=motion_detected,
        occupancy=bool(data.get("occupancy")),
        battery_pct=_int(data.get("battery_pct")),
        rssi_dbm=_int(data.get("rssi_dbm")),
        device_health=str(data.get("device_health") or "ok"),
        faults=faults or None,
    )
    db.add(event)

    levels = compute_levels(
        smoke_ppm=smoke_ppm,
        gas_ppm=gas_ppm,
        flame_detected=flame_detected,
        water_level=water_level,
        motion_detected=motion_detected,
    )
    old_levels = dict(device.sensor_levels or {})
    device.last_smoke_ppm = event.smoke_ppm
    device.last_gas_ppm = event.gas_ppm
    device.last_flame_detected = event.flame_detected
    device.last_water_level = event.water_level
    device.last_motion_detected = event.motion_detected
    device.last_occupancy = event.occupancy
    device.battery_pct = event.battery_pct
    device.rssi_dbm = event.rssi_dbm
    device.device_health = event.device_health
    device.sensor_levels = levels
    device.risk_level = device_risk_level(levels)
    device.last_seen_at = now

    if event.faults and device.faults != event.faults:
        db.add(
            Alert(
                property_id=device.property_id,
                device_id=device.device_id,
                signal="sensor_fault",
                severity="notice",
                status="open",
                notes=", ".join(event.faults),
                first_seen_at=now,
                last_seen_at=now,
            )
        )
        device.faults = event.faults

    created = apply_transitions(db, device, old_levels, levels, now)
    recompute_property_risk(db, device.property_id)
    dispatch_new_alerts(db, created)
    db.commit()
    return {"accepted": True, "sequence": sequence}
