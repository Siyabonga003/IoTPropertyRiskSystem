from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import Alert, Device
from app.risk import check_stale_devices
from tests.conftest import create_user, make_device


def test_stale_device_disconnects_with_fail_safe(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-stale-1", status="active")
    device = db.query(Device).filter_by(device_id="esp32-stale-1").one()
    device.last_seen_at = datetime.now(UTC) - timedelta(minutes=30)
    db.commit()
    check_stale_devices(db)
    db.expire_all()
    device = db.query(Device).filter_by(device_id="esp32-stale-1").one()
    assert device.status == "disconnected"
    assert device.risk_level == 4  # smoke_gas + flame fail-safe floors are critical
    alert = db.query(Alert).filter_by(device_id="esp32-stale-1", signal="device_disconnected").one()
    assert alert.severity == "warning"
    assert alert.status == "open"


def test_recent_device_not_marked(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-fresh-1", status="active")
    check_stale_devices(db)
    db.expire_all()
    device = db.query(Device).filter_by(device_id="esp32-fresh-1").one()
    assert device.status == "active"
