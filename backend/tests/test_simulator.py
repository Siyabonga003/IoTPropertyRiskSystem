from __future__ import annotations

import pytest

from app.models import Alert, Device
from simulator.simulator import Simulator
from tests.conftest import create_user, login, pair_start


def _pair_device(client, user, device_id):
    """Register the simulated device and claim its device_token via the real pairing flow (SPEC §3)."""
    r = pair_start(client, device_id)
    user_token = login(client, user.email)
    r = client.post("/api/v1/pair", json={"token": r["token"]}, headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 200, r.text
    data = r.json()
    return user_token, data["device_id"], data["property_id"], data["device_token"]


def _simulator(client, user_token, device_id, property_id, token):
    return Simulator(
        client,
        device_id=device_id,
        device_token=token,
        property_id=property_id,
        user_token=user_token,
        interval=0.05,
        verbose=False,
    )


def test_simulator_smoke_spike_creates_alert(client, db):
    """Simulated smoke spike flows through ingest → device readings → warning alert."""
    user, _prop = create_user(db)
    user_token, dev_id, property_id, token = _pair_device(client, user, "esp32-sim-1")
    sim = _simulator(client, user_token, dev_id, property_id, token)
    sim.run("smoke-spike", 2.0)
    db.expire_all()
    device = db.query(Device).filter_by(device_id=dev_id).one()
    assert device.last_smoke_ppm == pytest.approx(420.0)
    alert = db.query(Alert).filter_by(device_id=dev_id, signal="smoke_gas", status="open").one()
    assert alert.severity == "warning"


def test_simulator_motion_unarmed_gated_then_armed(client, db):
    """Motion while unarmed creates no alerts; after arming, a motion rise creates one."""
    user, _prop = create_user(db)
    user_token, dev_id, property_id, token = _pair_device(client, user, "esp32-sim-2")
    sim = _simulator(client, user_token, dev_id, property_id, token)
    sim.run("motion-unarmed", 21.0)
    db.expire_all()
    alerts = db.query(Alert).filter_by(device_id=dev_id, signal="motion").all()
    assert len(alerts) == 1
    assert alerts[0].status == "open"
    assert alerts[0].severity == "notice"


def test_simulator_motion_armed_creates_alert(client, db):
    """Motion rise while armed creates a notice alert (armed mode is set first)."""
    user, _prop = create_user(db)
    user_token, dev_id, property_id, token = _pair_device(client, user, "esp32-sim-3")
    sim = _simulator(client, user_token, dev_id, property_id, token)
    sim.run("motion-armed", 8.0)
    db.expire_all()
    alerts = db.query(Alert).filter_by(device_id=dev_id, signal="motion").all()
    assert len(alerts) >= 2
    assert any(a.status == "open" for a in alerts)
