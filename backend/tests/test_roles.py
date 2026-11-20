from __future__ import annotations

from app.models import Alert
from tests.conftest import create_user, ingest, login, make_device, make_device_token


def _alert_id(db, device_id):
    return db.query(Alert).filter_by(device_id=device_id).one().id


def test_viewer_read_only(client, db):
    _user, prop = create_user(db, role="viewer")
    make_device(db, prop.id, "esp32-view-1")
    tok = login(client, "alice@example.com")
    assert client.get("/api/v1/devices", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    assert client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    assert client.get("/api/v1/devices/esp32-view-1", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    r = client.delete("/api/v1/devices/esp32-view-1", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_responder_can_ack_not_revoke(client, db):
    _user, prop = create_user(db, role="responder")
    make_device(db, prop.id, "esp32-resp-1")
    token = make_device_token(db, "esp32-resp-1")
    ingest(client, "esp32-resp-1", token, 1, smoke_ppm=400)
    alert_id = _alert_id(db, "esp32-resp-1")
    tok = login(client, "alice@example.com")
    r = client.post(f"/api/v1/alerts/{alert_id}/ack", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    r2 = client.delete("/api/v1/devices/esp32-resp-1", headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 403


def test_admin_can_revoke(client, db):
    _user, prop = create_user(db, role="admin")
    make_device(db, prop.id, "esp32-admin-1")
    r = client.delete("/api/v1/devices/esp32-admin-1", headers={"Authorization": f"Bearer {login(client, 'alice@example.com')}"})
    assert r.status_code == 200
    assert r.json()["status"] == "revoked"


def test_owner_can_revoke(client, db):
    _user, prop = create_user(db, role="owner")
    make_device(db, prop.id, "esp32-owner-1")
    r = client.delete("/api/v1/devices/esp32-owner-1", headers={"Authorization": f"Bearer {login(client, 'alice@example.com')}"})
    assert r.status_code == 200


def test_revoked_device_rejected_on_ingest(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-rev-1")
    token = make_device_token(db, "esp32-rev-1")
    client.delete("/api/v1/devices/esp32-rev-1", headers={"Authorization": f"Bearer {login(client, 'alice@example.com')}"})
    r = ingest(client, "esp32-rev-1", token, 1, smoke_ppm=0)
    assert r.status_code == 401


def test_unauthenticated_requests_rejected(client):
    assert client.get("/api/v1/devices").status_code == 401
    assert client.get("/api/v1/alerts").status_code == 401
    assert client.post("/api/v1/ingest/telemetry", json={"device_id": "x", "sequence": 1}).status_code == 401
