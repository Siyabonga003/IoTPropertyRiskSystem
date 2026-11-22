from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.config import config
from app.models import Alert, Device, Property, current_system_mode, utcnow
from app.thresholds import Level, device_risk_level

# Fail-safe risk contribution per signal when a device is marked disconnected
# (conservative: assumes the sensor could be failing in the worst way).
FAILSAFE_DISCONNECT_RISK: dict[str, int] = {
    "smoke_gas": Level.CRITICAL,
    "flame": Level.CRITICAL,
    "water_leak": Level.WARNING,
    "motion": Level.NOTICE,
}


def as_utc(dt: datetime | None) -> datetime | None:
    """Normalize a datetime to aware UTC (SQLite returns naive datetimes)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def apply_fail_safe(db, device: Device) -> None:
    """Raise each signal's level to its fail-safe floor for a disconnected device."""
    levels = dict(device.sensor_levels or {})
    for signal, floor in FAILSAFE_DISCONNECT_RISK.items():
        if levels.get(signal, Level.OK) < floor:
            levels[signal] = floor
    device.sensor_levels = levels
    device.risk_level = device_risk_level(levels)


def recompute_property_risk(db, property_id: str | None) -> int:
    """Set the property risk to the max device risk in the property."""
    if not property_id:
        return 0
    prop = db.get(Property, property_id)
    if prop is None:
        return 0
    devices = db.query(Device).filter(Device.property_id == property_id, Device.status != "revoked").all()
    risk = max((d.risk_level or 0 for d in devices), default=0)
    prop.risk_level = risk
    db.add(prop)
    return risk


def check_stale_devices(db) -> list[Device]:
    """Mark active devices with no telemetry within the timeout as disconnected."""
    now = utcnow()
    stale: list[Device] = []
    devices = db.query(Device).filter_by(status="active").all()
    for device in devices:
        last_seen = as_utc(device.last_seen_at) or as_utc(device.paired_at)
        if last_seen is not None and now - last_seen > timedelta(minutes=config.TELEMETRY_TIMEOUT_MINUTES):
            device.status = "disconnected"
            apply_fail_safe(db, device)
            db.add(
                Alert(
                    property_id=device.property_id,
                    device_id=device.device_id,
                    signal="device_disconnected",
                    severity="warning",
                    status="open",
                    armed_mode=current_system_mode(db, device.property_id),
                    first_seen_at=now,
                    last_seen_at=now,
                    notes="Device disconnected: no telemetry within the timeout.",
                )
            )
            recompute_property_risk(db, device.property_id)
            stale.append(device)
    db.commit()
    return stale
