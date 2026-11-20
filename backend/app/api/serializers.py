from __future__ import annotations

from datetime import UTC
from typing import Any

from app.models import Alert, Device, TelemetryEvent, User


def iso(dt) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "created_at": iso(user.created_at),
    }


def serialize_property(prop) -> dict[str, Any]:
    return {"id": prop.id, "name": prop.name, "risk_level": prop.risk_level}


def serialize_device(device: Device) -> dict[str, Any]:
    return {
        "device_id": device.device_id,
        "property_id": device.property_id,
        "name": device.name,
        "firmware_version": device.firmware_version,
        "status": device.status,
        "paired_at": iso(device.paired_at),
        "last_seen_at": iso(device.last_seen_at),
        "risk_level": device.risk_level,
        "sensor_levels": device.sensor_levels or {},
        "last_smoke_ppm": device.last_smoke_ppm,
        "last_gas_ppm": device.last_gas_ppm,
        "last_flame_detected": device.last_flame_detected,
        "last_water_level": device.last_water_level,
        "last_motion_detected": device.last_motion_detected,
        "last_occupancy": device.last_occupancy,
        "battery_pct": device.battery_pct,
        "rssi_dbm": device.rssi_dbm,
        "device_health": device.device_health,
        "faults": device.faults,
    }


def serialize_event(event: TelemetryEvent) -> dict[str, Any]:
    return {
        "device_id": event.device_id,
        "sequence": event.sequence,
        "property_id": event.property_id,
        "timestamp": iso(event.timestamp),
        "received_at": iso(event.received_at),
        "smoke_ppm": event.smoke_ppm,
        "gas_ppm": event.gas_ppm,
        "flame_detected": event.flame_detected,
        "water_level": event.water_level,
        "motion_detected": event.motion_detected,
        "occupancy": event.occupancy,
        "battery_pct": event.battery_pct,
        "rssi_dbm": event.rssi_dbm,
        "device_health": event.device_health,
        "device_risk": event.device_risk,
        "faults": event.faults,
    }


def serialize_alert(alert: Alert) -> dict[str, Any]:
    return {
        "id": alert.id,
        "property_id": alert.property_id,
        "device_id": alert.device_id,
        "signal": alert.signal,
        "severity": alert.severity,
        "status": alert.status,
        "notes": alert.notes,
        "first_seen_at": iso(alert.first_seen_at),
        "last_seen_at": iso(alert.last_seen_at),
        "acknowledged_at": iso(alert.acknowledged_at),
        "resolved_at": iso(alert.resolved_at),
    }
