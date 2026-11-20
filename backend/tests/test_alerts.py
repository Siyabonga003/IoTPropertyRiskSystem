from __future__ import annotations

from app.models import Alert, AlertNotification
from tests.conftest import create_user, ingest, login, make_device, make_device_token


def test_alerts_list_and_ack(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-alert-1")
    token = make_device_token(db, "esp32-alert-1")
    ingest(client, "esp32-alert-1", token, 1, smoke_ppm=400)
    user_token = login(client, "alice@example.com")
    r = client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["signal"] == "smoke_gas"
    assert items[0]["status"] == "open"
    alert_id = items[0]["id"]
    r2 = client.get(f"/api/v1/alerts/{alert_id}", headers={"Authorization": f"Bearer {user_token}"})
    assert r2.status_code == 200
    r3 = client.get("/api/v1/alerts?status=open", headers={"Authorization": f"Bearer {user_token}"})
    assert len(r3.json()["items"]) == 1
    r4 = client.post(f"/api/v1/alerts/{alert_id}/ack", headers={"Authorization": f"Bearer {user_token}"})
    assert r4.status_code == 200
    assert r4.json()["status"] == "acknowledged"
    r5 = client.get("/api/v1/alerts?status=open", headers={"Authorization": f"Bearer {user_token}"})
    assert r5.json()["items"] == []


def test_alerts_not_visible_to_other_property(client, db):
    _alice, alice_prop = create_user(db, email="alice@example.com", name="Alice", property_name="Alice Home")
    create_user(db, email="bob@example.com", name="Bob", property_name="Bob Home")
    make_device(db, alice_prop.id, "esp32-alert-2")
    token = make_device_token(db, "esp32-alert-2")
    ingest(client, "esp32-alert-2", token, 1, smoke_ppm=400)
    r = client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {login(client, 'bob@example.com')}"})
    assert r.json()["items"] == []


def test_notifications_created_for_subscribers(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-notify-1")
    token = make_device_token(db, "esp32-notify-1")
    ingest(client, "esp32-notify-1", token, 1, smoke_ppm=400)
    db.expire_all()
    alert = db.query(Alert).filter_by(device_id="esp32-notify-1").one()
    notifications = db.query(AlertNotification).filter_by(alert_id=alert.id).all()
    assert [n.channel for n in notifications] == ["push"]
    assert notifications[0].status == "sent"
