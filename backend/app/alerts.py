from __future__ import annotations

from datetime import datetime

from app.models import UNARMED, Alert, Device, current_system_mode
from app.notifications import dispatch_alert
from app.thresholds import SEVERITY_NAMES, SEVERITY_RANK, SIGNALS


def apply_transitions(
    db,
    device: Device,
    old_levels: dict[str, int] | None,
    new_levels: dict[str, int],
    now: datetime,
) -> list[Alert]:
    """Create alerts when a signal rises a level; resolve open alerts when it drops."""
    created: list[Alert] = []
    old = old_levels or {}
    mode = current_system_mode(db, device.property_id)
    for signal in SIGNALS:
        old_level = old.get(signal, 0)
        new_level = new_levels.get(signal, 0)
        if signal == "motion" and mode == UNARMED and new_level > 0 and old_level == 0:
            # Unarmed: motion never creates new alerts (SPEC §2 — system arming modes).
            continue
        if new_level > old_level:
            open_alerts = db.query(Alert).filter_by(device_id=device.device_id, signal=signal, status="open").all()
            for alert in open_alerts:
                alert.status = "resolved"
                alert.resolved_at = now
            if new_level > 0:
                alert = Alert(
                    property_id=device.property_id,
                    device_id=device.device_id,
                    signal=signal,
                    severity=SEVERITY_NAMES[new_level],
                    status="open",
                    notes="",
                    armed_mode=mode,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                db.add(alert)
                created.append(alert)
        elif new_level < old_level:
            open_alerts = db.query(Alert).filter_by(device_id=device.device_id, signal=signal, status="open").all()
            for alert in open_alerts:
                if SEVERITY_RANK[alert.severity] > new_level:
                    alert.status = "resolved"
                    alert.resolved_at = now
    return created


def dispatch_new_alerts(db, alerts: list[Alert]) -> None:
    for alert in alerts:
        dispatch_alert(db, alert)
