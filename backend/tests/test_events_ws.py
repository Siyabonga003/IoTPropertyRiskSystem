from __future__ import annotations

import time

from tests.conftest import create_user, ingest, login, make_device, make_device_token


def test_events_endpoint(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-evt-1")
    token = make_device_token(db, "esp32-evt-1")
    ingest(client, "esp32-evt-1", token, 7, smoke_ppm=500)
    r = client.get("/api/v1/devices/esp32-evt-1/events", headers={"Authorization": f"Bearer {login(client, 'alice@example.com')}"})
    assert r.status_code == 200
    assert any(e["sequence"] == 7 for e in r.json()["events"])


def test_websocket_stream(client, db):
    _user, prop = create_user(db)
    make_device(db, prop.id, "esp32-ws-1")
    token = login(client, "alice@example.com")
    with client.websocket_connect(f"/api/v1/devices/esp32-ws-1/stream?token={token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "connected"
        dtok = make_device_token(db, "esp32-ws-1")
        ingest(client, "esp32-ws-1", dtok, 1, smoke_ppm=400)
        got = None
        deadline = time.time() + 5
        while time.time() < deadline:
            got = ws.receive_json()
            if got["type"] == "telemetry":
                break
        assert got is not None and got["type"] == "telemetry"
        assert got["payload"]["sequence"] == 1
