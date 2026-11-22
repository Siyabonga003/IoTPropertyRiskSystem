from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from app.alerts import apply_transitions, dispatch_new_alerts
from app.api.validation import clamp_int, finite_number, json_object
from app.database import get_db
from app.models import (
    SYSTEM_MODES,
    Alert,
    Device,
    SystemMode,
    TelemetryEvent,
    current_system_mode,
    set_system_mode,
    utcnow,
)
from app.risk import recompute_property_risk
from app.security import get_current_device
from app.thresholds import compute_levels, device_risk_level

router = APIRouter()


_HEALTH_VALUES = {"ok", "degraded", "fault", "disconnected"}
_MAX_FAULTS = 20
_MAX_FAULT_LEN = 64


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _as_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    return default


def _clean_faults(value) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()[:_MAX_FAULT_LEN]
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= _MAX_FAULTS:
            break
    return cleaned


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
    # A disconnected device is allowed to recover: its next telemetry brings it
    # back to `active` and resolves the open `device_disconnected` alert.
    if device.status not in ("active", "disconnected") or not device.property_id:
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")
    data = await json_object(request)
    sequence = data.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence <= 0:
        raise HTTPException(status_code=422, detail="sequence must be a positive integer")
    raw_armed = data.get("armed_mode")
    if raw_armed is None:
        # Not reported by the device — keep the current mode.
        armed_mode = current_system_mode(db, device.property_id)
    else:
        armed_mode = str(raw_armed)
        if armed_mode not in SYSTEM_MODES:
            raise HTTPException(status_code=422, detail="armed_mode must be one of: " + ", ".join(SYSTEM_MODES))
    device_health = data.get("device_health") or "ok"
    if not isinstance(device_health, str) or device_health not in _HEALTH_VALUES:
        raise HTTPException(
            status_code=422,
            detail="device_health must be one of: " + ", ".join(sorted(_HEALTH_VALUES)),
        )
    existing = (
        db.query(TelemetryEvent)
        .filter_by(device_id=device.device_id, sequence=sequence)
        .one_or_none()
    )
    if existing is not None:
        return {"accepted": False, "reason": "stale_sequence", "sequence": sequence}

    now = utcnow()
    # SPEC §1: sensors are reported under the nested `sensors` object; fall back
    # to flat fields for older firmware/tests.
    raw_sensors = data.get("sensors")
    if raw_sensors is not None and not isinstance(raw_sensors, dict):
        raise HTTPException(status_code=422, detail="sensors must be an object")
    sensors = raw_sensors or {}
    for key in ("smoke_gas", "flame", "water_leak", "motion"):
        if key in sensors and not isinstance(sensors[key], dict):
            raise HTTPException(status_code=422, detail=f"sensors.{key} must be an object")
    smoke_gas = _as_dict(sensors.get("smoke_gas"))
    flame = _as_dict(sensors.get("flame"))
    water_leak = _as_dict(sensors.get("water_leak"))
    motion = _as_dict(sensors.get("motion"))
    smoke_ppm = finite_number(smoke_gas.get("smoke_ppm", data.get("smoke_ppm")))
    gas_ppm = finite_number(smoke_gas.get("gas_ppm", data.get("gas_ppm")))
    if smoke_ppm is not None:
        smoke_ppm = max(0.0, min(smoke_ppm, 100_000.0))
    if gas_ppm is not None:
        gas_ppm = max(0.0, min(gas_ppm, 100_000.0))
    flame_detected = _as_bool(flame.get("detected", data.get("flame_detected")))
    water_level = clamp_int(water_leak.get("level", data.get("water_level")), 0, 100)
    if water_level is None and _as_bool(water_leak.get("detected", data.get("water_leak_detected"))):
        # Digital leak sensor without an analog level: report minimal detection.
        water_level = 1
    motion_detected = _as_bool(motion.get("motion_detected", data.get("motion_detected")))
    occupancy = _as_bool(motion.get("occupancy", data.get("occupancy")))
    faults = _clean_faults(data.get("faults"))
    timestamp = _parse_ts(data.get("timestamp")) or now
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    event = TelemetryEvent(
        device_id=device.device_id,
        property_id=device.property_id,
        sequence=sequence,
        timestamp=timestamp,
        received_at=now,
        smoke_ppm=smoke_ppm,
        gas_ppm=gas_ppm,
        flame_detected=flame_detected,
        water_level=water_level if water_level is not None else 0,
        motion_detected=motion_detected,
        occupancy=occupancy,
        battery_pct=clamp_int(data.get("battery_pct"), 0, 100),
        rssi_dbm=clamp_int(data.get("rssi_dbm"), -200, 0),
        device_health=device_health,
        armed_mode=armed_mode,
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
    event.device_risk = device.risk_level
    device.last_seen_at = now
    device.status = "active"
    if raw_armed is not None and db.get(SystemMode, device.property_id) is None:
        # The backend is authoritative for mode changes (PUT /system/modes).
        # Device reports only initialize the row; a stale report (e.g. buffered
        # telemetry from before a user change) must not revert the mode.
        set_system_mode(db, device.property_id, armed_mode, changed_by=device.device_id, reason="device-reported mode")

    # Reconnection clears the fail-safe disconnect alert.
    for alert in db.query(Alert).filter_by(
        device_id=device.device_id, signal="device_disconnected", status="open"
    ):
        alert.status = "resolved"
        alert.resolved_at = now

    created: list[Alert] = []
    # Sensor faults: replace the open fault alert when the list changes, and
    # resolve it when the device reports no faults again.
    if faults != (device.faults or []):
        for alert in db.query(Alert).filter_by(
            device_id=device.device_id, signal="sensor_fault", status="open"
        ):
            alert.status = "resolved"
            alert.resolved_at = now
        if faults:
            fault_alert = Alert(
                property_id=device.property_id,
                device_id=device.device_id,
                signal="sensor_fault",
                severity="notice",
                status="open",
                notes=", ".join(faults),
                armed_mode=armed_mode,
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(fault_alert)
            created.append(fault_alert)
        device.faults = faults or None

    created.extend(apply_transitions(db, device, old_levels, levels, now))
    recompute_property_risk(db, device.property_id)
    dispatch_new_alerts(db, created)
    db.commit()
    return {"accepted": True, "sequence": sequence}
