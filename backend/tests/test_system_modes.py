from __future__ import annotations

from app.models import (
    ARMED,
    ARMED_AWAY,
    UNARMED,
    Alert,
    PropertyMember,
    SystemMode,
    SystemModeHistory,
    TelemetryEvent,
)
from tests.conftest import create_user, ingest, login, make_device, make_device_token


def _put_mode(client, user, prop, mode):
    token = login(client, user.email)
    r = client.put(
        f"/api/v1/system/modes/{prop.id}",
        json={"mode": mode},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _get_modes(client, user):
    r = client.get("/api/v1/system/modes", headers={"Authorization": f"Bearer {login(client, user.email)}"})
    assert r.status_code == 200, r.text
    return r.json()


def test_get_modes_default_unarmed(client, db):
    user, prop = create_user(db)
    items = _get_modes(client, user)
    assert items == [{"property_id": prop.id, "mode": UNARMED, "updated_at": None, "updated_by": None}]


def test_set_mode_owner(client, db):
    user, prop = create_user(db)
    body = _put_mode(client, user, prop, ARMED)
    assert body["mode"] == ARMED
    row = db.get(SystemMode, prop.id)
    assert row is not None and row.mode == ARMED
    hist = db.query(SystemModeHistory).filter_by(property_id=prop.id).all()
    assert [h.mode for h in hist] == [ARMED]
    assert hist[0].changed_by == user.id


def test_set_mode_viewer_forbidden(client, db):
    _user, prop = create_user(db)
    viewer, _ = create_user(db, email="viewer@example.com", name="Viewer", role="viewer", property_name="Viewer Home")
    db.add(PropertyMember(user_id=viewer.id, property_id=prop.id, role="viewer"))
    db.commit()
    token = login(client, viewer.email)
    r = client.put(f"/api/v1/system/modes/{prop.id}", json={"mode": ARMED}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    # Viewers can read modes.
    r2 = client.get("/api/v1/system/modes", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200


def test_set_mode_unauthorized(client, db):
    _user, prop = create_user(db)
    r = client.put(f"/api/v1/system/modes/{prop.id}", json={"mode": ARMED})
    assert r.status_code == 401


def test_set_mode_invalid(client, db):
    user, prop = create_user(db)
    token = login(client, user.email)
    r = client.put(f"/api/v1/system/modes/{prop.id}", json={"mode": "nonsense"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422
    r = client.put(f"/api/v1/system/modes/{prop.id}", json={}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422
    r = client.put(f"/api/v1/system/modes/{prop.id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422


def test_set_mode_other_property_not_found(client, db):
    _alice, alice_prop = create_user(db)
    bob, _ = create_user(db, email="bob@example.com", name="Bob", property_name="Bob Home")
    token = login(client, bob.email)
    r = client.put(f"/api/v1/system/modes/{alice_prop.id}", json={"mode": ARMED}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_mode_history_endpoint(client, db):
    user, prop = create_user(db)
    _put_mode(client, user, prop, ARMED)
    _put_mode(client, user, prop, UNARMED)
    _put_mode(client, user, prop, ARMED_AWAY)
    r = client.get(f"/api/v1/system/modes/{prop.id}/history", headers={"Authorization": f"Bearer {login(client, user.email)}"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert [h["mode"] for h in items] == [ARMED_AWAY, UNARMED, ARMED]
    assert all(h["changed_by"] == user.id for h in items)


def test_responder_can_view_mode_history(client, db):
    _owner, prop = create_user(db)
    responder, _ = create_user(db, email="responder@example.com", name="Responder", role="responder")
    db.add(PropertyMember(user_id=responder.id, property_id=prop.id, role="responder"))
    db.commit()
    token = login(client, responder.email)
    r = client.get(f"/api/v1/system/modes/{prop.id}/history", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"items": []}


def test_device_mode_endpoint(client, db):
    user, prop = create_user(db)
    make_device(db, prop.id, "esp32-mode-1")
    token = make_device_token(db, "esp32-mode-1")
    r = client.get("/api/v1/devices/esp32-mode-1/mode", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"mode": UNARMED}
    _put_mode(client, user, prop, ARMED)
    r = client.get("/api/v1/devices/esp32-mode-1/mode", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["mode"] == ARMED


def test_motion_gated_when_unarmed(client, db):
    user, prop = create_user(db)
    make_device(db, prop.id, "esp32-motion-1")
    token = make_device_token(db, "esp32-motion-1")
    # Unarmed: motion detected → no alert.
    assert ingest(client, "esp32-motion-1", token, 1, motion_detected=True).status_code == 200
    assert db.query(Alert).filter_by(device_id="esp32-motion-1", signal="motion").count() == 0
    # Arm via API; motion drops, then rises while armed → alert.
    _put_mode(client, user, prop, ARMED)
    assert ingest(client, "esp32-motion-1", token, 2, motion_detected=False).status_code == 200
    assert ingest(client, "esp32-motion-1", token, 3, motion_detected=True).status_code == 200
    alert = db.query(Alert).filter_by(device_id="esp32-motion-1", signal="motion").one()
    assert alert.severity == "notice"
    assert alert.status == "open"


def test_armed_mode_stored_on_telemetry(client, db):
    user, prop = create_user(db)
    make_device(db, prop.id, "esp32-am-1")
    token = make_device_token(db, "esp32-am-1")
    r = ingest(client, "esp32-am-1", token, 1, armed_mode=ARMED_AWAY, smoke_ppm=0)
    assert r.status_code == 200
    db.expire_all()
    event = db.query(TelemetryEvent).filter_by(device_id="esp32-am-1").one()
    assert event.armed_mode == ARMED_AWAY
    items = _get_modes(client, user)
    assert items[0]["mode"] == ARMED_AWAY


def test_invalid_armed_mode_rejected(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-am-2")
    token = make_device_token(db, "esp32-am-2")
    assert ingest(client, "esp32-am-2", token, 1, armed_mode="bogus").status_code == 422


def test_user_mode_not_reverted_by_device_report(client, db):
    user, prop = create_user(db)
    make_device(db, prop.id, "esp32-am-3")
    token = make_device_token(db, "esp32-am-3")
    _put_mode(client, user, prop, ARMED)
    # A stale/buffered device report must not override the user's selection.
    assert ingest(client, "esp32-am-3", token, 1, armed_mode=UNARMED, smoke_ppm=0).status_code == 200
    assert _get_modes(client, user)[0]["mode"] == ARMED


def test_smoke_alerts_unaffected_by_unarmed(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-smoke-am")
    token = make_device_token(db, "esp32-smoke-am")
    assert ingest(client, "esp32-smoke-am", token, 1, smoke_ppm=400).status_code == 200
    alert = db.query(Alert).filter_by(device_id="esp32-smoke-am", signal="smoke_gas").one()
    assert alert.status == "open"
