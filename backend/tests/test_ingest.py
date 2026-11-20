from __future__ import annotations

from app.models import Alert, Device, Property, TelemetryEvent
from app.thresholds import Level
from tests.conftest import create_user, ingest, make_device, make_device_token


def test_smoke_warning_alert(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-smoke-1")
    token = make_device_token(db, "esp32-smoke-1")
    r = ingest(client, "esp32-smoke-1", token, 1, smoke_ppm=400)
    assert r.status_code == 200
    assert r.json() == {"accepted": True, "sequence": 1}
    db.expire_all()
    device = db.query(Device).filter_by(device_id="esp32-smoke-1").one()
    assert device.risk_level == Level.WARNING
    assert device.sensor_levels["smoke_gas"] == Level.WARNING
    alert = db.query(Alert).filter_by(device_id="esp32-smoke-1").one()
    assert alert.signal == "smoke_gas"
    assert alert.severity == "warning"
    assert alert.status == "open"
    event = db.query(TelemetryEvent).filter_by(device_id="esp32-smoke-1").one()
    assert event.smoke_ppm == 400


def test_smoke_critical(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-smoke-2")
    token = make_device_token(db, "esp32-smoke-2")
    r = ingest(client, "esp32-smoke-2", token, 1, smoke_ppm=1200)
    assert r.status_code == 200
    db.expire_all()
    device = db.query(Device).filter_by(device_id="esp32-smoke-2").one()
    assert device.risk_level == Level.CRITICAL
    alert = db.query(Alert).filter_by(device_id="esp32-smoke-2").one()
    assert alert.severity == "critical"


def test_smoke_recovery_resolves(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-smoke-3")
    token = make_device_token(db, "esp32-smoke-3")
    assert ingest(client, "esp32-smoke-3", token, 1, smoke_ppm=400).status_code == 200
    assert ingest(client, "esp32-smoke-3", token, 2, smoke_ppm=100).status_code == 200
    db.expire_all()
    device = db.query(Device).filter_by(device_id="esp32-smoke-3").one()
    assert device.risk_level == Level.OK
    alert = db.query(Alert).filter_by(device_id="esp32-smoke-3").one()
    assert alert.status == "resolved"
    assert alert.resolved_at is not None


def test_flame_critical(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-flame-1")
    token = make_device_token(db, "esp32-flame-1")
    r = ingest(client, "esp32-flame-1", token, 1, flame_detected=True)
    assert r.status_code == 200
    db.expire_all()
    device = db.query(Device).filter_by(device_id="esp32-flame-1").one()
    assert device.risk_level == Level.CRITICAL
    alert = db.query(Alert).filter_by(device_id="esp32-flame-1").one()
    assert alert.signal == "flame"
    assert alert.severity == "critical"


def test_water_leak_alert(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-water-1")
    token = make_device_token(db, "esp32-water-1")
    r = ingest(client, "esp32-water-1", token, 1, water_level=30)
    assert r.status_code == 200
    db.expire_all()
    device = db.query(Device).filter_by(device_id="esp32-water-1").one()
    assert device.risk_level == Level.ALERT
    alert = db.query(Alert).filter_by(device_id="esp32-water-1").one()
    assert alert.signal == "water_leak"
    assert alert.severity == "alert"


def test_motion_notice(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-motion-1")
    token = make_device_token(db, "esp32-motion-1")
    r = ingest(client, "esp32-motion-1", token, 1, motion_detected=True)
    assert r.status_code == 200
    db.expire_all()
    device = db.query(Device).filter_by(device_id="esp32-motion-1").one()
    assert device.risk_level == Level.NOTICE
    alert = db.query(Alert).filter_by(device_id="esp32-motion-1").one()
    assert alert.signal == "motion"
    assert alert.severity == "notice"


def test_duplicate_sequence_rejected(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-dup-1")
    token = make_device_token(db, "esp32-dup-1")
    r1 = ingest(client, "esp32-dup-1", token, 5, smoke_ppm=0)
    assert r1.json()["accepted"] is True
    r2 = ingest(client, "esp32-dup-1", token, 5, smoke_ppm=500)
    assert r2.status_code == 200
    assert r2.json() == {"accepted": False, "reason": "stale_sequence", "sequence": 5}
    assert db.query(TelemetryEvent).filter_by(device_id="esp32-dup-1", sequence=5).count() == 1


def test_invalid_sequence_rejected(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-inv-1")
    token = make_device_token(db, "esp32-inv-1")
    assert ingest(client, "esp32-inv-1", token, 0).status_code == 422
    r = client.post(
        "/api/v1/ingest/telemetry",
        json={"device_id": "esp32-inv-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_unknown_device_token_rejected(client):
    r = ingest(client, "esp32-ghost", "dt_bogus", 1, smoke_ppm=0)
    assert r.status_code == 401


def test_property_risk_updated(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-risk-1")
    token = make_device_token(db, "esp32-risk-1")
    ingest(client, "esp32-risk-1", token, 1, smoke_ppm=400)
    db.expire_all()
    p = db.query(Property).filter_by(id=prop.id).one()
    assert p.risk_level == Level.WARNING


def test_sensor_faults_create_alert(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-fault-1")
    token = make_device_token(db, "esp32-fault-1")
    r = ingest(client, "esp32-fault-1", token, 1, faults=["heater_timeout", "sensor_error"])
    assert r.status_code == 200
    db.expire_all()
    device = db.query(Device).filter_by(device_id="esp32-fault-1").one()
    assert device.faults == ["heater_timeout", "sensor_error"]
    alert = db.query(Alert).filter_by(device_id="esp32-fault-1", signal="sensor_fault").one()
    assert alert.severity == "notice"
    assert "heater_timeout" in alert.notes
