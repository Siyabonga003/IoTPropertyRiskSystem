from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import Device, PairingToken
from app.risk import as_utc
from app.security import hash_token
from tests.conftest import create_user, login, pair_start


def test_pair_start_creates_token(client, db):
    r = client.post("/api/v1/devices/esp32-p1/pair-start")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["device_id"] == "esp32-p1"
    assert data["token"].startswith("pt_")
    assert data["qr_url"] == f"http://localhost:8000/pair?token={data['token']}"
    assert data["expires_at"]
    device = db.query(Device).filter_by(device_id="esp32-p1").one()
    assert device.status == "pairing"
    pairing = db.query(PairingToken).filter_by(token_hash=hash_token(data["token"])).one()
    assert as_utc(pairing.expires_at) > datetime.now(UTC)


def test_pair_status_before_claim(client, db):
    data = pair_start(client, "esp32-p2")
    r = client.get("/api/v1/devices/esp32-p2/pair-status", headers={"Authorization": f"Bearer {data['token']}"})
    assert r.status_code == 200
    assert r.json() == {"status": "pairing"}


def test_pair_status_invalid_token(client):
    r = client.get("/api/v1/devices/esp32-p3/pair-status", headers={"Authorization": "Bearer pt_bogus"})
    assert r.status_code == 401


def test_pair_claim_issues_device_token(client, db):
    create_user(db, email="bob@example.com", name="Bob")
    data = pair_start(client, "esp32-p4")
    r = client.post(
        "/api/v1/pair",
        json={"token": data["token"]},
        headers={"Authorization": f"Bearer {login(client, 'bob@example.com')}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["device_id"] == "esp32-p4"
    assert body["property_id"]
    assert body["device_token"].startswith("dt_")
    db.expire_all()
    device = db.query(Device).filter_by(device_id="esp32-p4").one()
    assert device.status == "active"
    assert device.property_id == body["property_id"]
    assert device.paired_at is not None
    r2 = client.get("/api/v1/devices/esp32-p4/pair-status", headers={"Authorization": f"Bearer {data['token']}"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "active"
    assert r2.json()["device_token"] == body["device_token"]


def test_pair_claim_invalid_token(client, db):
    create_user(db, email="carol@example.com", name="Carol")
    r = client.post(
        "/api/v1/pair",
        json={"token": "pt_bogus"},
        headers={"Authorization": f"Bearer {login(client, 'carol@example.com')}"},
    )
    assert r.status_code == 401


def test_pair_claim_twice_rejected(client, db):
    create_user(db, email="dave@example.com", name="Dave")
    data = pair_start(client, "esp32-p5")
    r = client.post("/api/v1/pair", json={"token": data["token"]}, headers={"Authorization": f"Bearer {login(client, 'dave@example.com')}"})
    assert r.status_code == 200
    r2 = client.post("/api/v1/pair", json={"token": data["token"]}, headers={"Authorization": f"Bearer {login(client, 'dave@example.com')}"})
    assert r2.status_code == 401


def test_pair_expired_token(client, db):
    data = pair_start(client, "esp32-p6")
    pairing = db.query(PairingToken).filter_by(token_hash=hash_token(data["token"])).one()
    pairing.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    r = client.get("/api/v1/devices/esp32-p6/pair-status", headers={"Authorization": f"Bearer {data['token']}"})
    assert r.status_code == 401
