from __future__ import annotations

from app.models import Alert
from tests.conftest import create_user, ingest, login, make_device, make_device_token


def test_user_scoped_to_property(client, db):
    _alice, alice_prop = create_user(db, email="alice@example.com", name="Alice", property_name="Alice Home")
    create_user(db, email="bob@example.com", name="Bob", property_name="Bob Home")
    make_device(db, alice_prop.id, "esp32-mt-a")
    alice_tok = login(client, "alice@example.com")
    r = client.get("/api/v1/devices", headers={"Authorization": f"Bearer {alice_tok}"})
    assert r.status_code == 200
    assert [d["device_id"] for d in r.json()] == ["esp32-mt-a"]
    assert client.get("/api/v1/devices/esp32-mt-a", headers={"Authorization": f"Bearer {alice_tok}"}).status_code == 200
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {alice_tok}"}).status_code == 200
    assert client.get(f"/api/v1/properties/{alice_prop.id}", headers={"Authorization": f"Bearer {alice_tok}"}).status_code == 200


def test_user_cannot_see_other_property_data(client, db):
    _alice, alice_prop = create_user(db, email="alice@example.com", name="Alice", property_name="Alice Home")
    create_user(db, email="bob@example.com", name="Bob", property_name="Bob Home")
    make_device(db, alice_prop.id, "esp32-mt-a")
    make_device(db, db_query_bob_property(db), "esp32-mt-b", status="pairing") if False else None
    alice_tok = login(client, "alice@example.com")
    bob_tok = login(client, "bob@example.com")
    # device-side ingest (token credential) creates an alert in Alice's property
    token_a = make_device_token(db, "esp32-mt-a")
    assert ingest(client, "esp32-mt-a", token_a, 1, smoke_ppm=400).status_code == 200
    # Bob cannot see Alice's device
    r = client.get("/api/v1/devices", headers={"Authorization": f"Bearer {bob_tok}"})
    assert all(d["property_id"] != alice_prop.id for d in r.json())
    # Bob cannot see Alice's device detail or status
    assert client.get("/api/v1/devices/esp32-mt-a", headers={"Authorization": f"Bearer {bob_tok}"}).status_code == 404
    assert client.get("/api/v1/devices/esp32-mt-a/status", headers={"Authorization": f"Bearer {bob_tok}"}).status_code == 404
    assert client.delete("/api/v1/devices/esp32-mt-a", headers={"Authorization": f"Bearer {bob_tok}"}).status_code == 404
    # Bob cannot see Alice's alerts
    r2 = client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {bob_tok}"})
    assert all(a["property_id"] != alice_prop.id for a in r2.json()["items"])
    # Alice sees her own alert
    r3 = client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {alice_tok}"})
    assert any(a["device_id"] == "esp32-mt-a" for a in r3.json()["items"])
    # Bob cannot acknowledge Alice's alerts (404: not visible to him, ack stays open)
    open_alert_id = next(a["id"] for a in r3.json()["items"] if a["status"] == "open")
    assert client.post(f"/api/v1/alerts/{open_alert_id}/ack", headers={"Authorization": f"Bearer {bob_tok}"}).status_code == 404
    alert = db.query(Alert).filter_by(id=open_alert_id).one()
    assert alert.status == "open"


def db_query_bob_property(db):
    return None
