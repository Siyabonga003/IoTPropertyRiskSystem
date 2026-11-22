# Backend — IoT Property Risk Monitoring API

FastAPI + SQLAlchemy backend for the four-sensor property risk system (smoke/gas,
flame, water leak, motion) with per-property arming modes. The wire contracts,
alert thresholds, pairing flow, and role matrix live in
[`docs/SPEC.md`](../docs/SPEC.md); this README covers installing, configuring,
migrating, testing, running, and demoing this backend.

## 1. Requirements and installation

- Python **3.12+** (`pyproject.toml` requires `>=3.12`).
- Runtime dependencies are declared in `pyproject.toml`: FastAPI, Uvicorn,
  SQLAlchemy, Alembic, PyJWT, and HTTPX. The `dev` extra adds pytest and ruff.
- The existing `backend/.venv` was created with uv. From `backend/`:

```bash
uv venv --python 3.12 .venv
uv pip install -e '.[dev]'
```

Verify the interpreter and dependencies:

```bash
.venv/bin/python -c "import fastapi, sqlalchemy, alembic, jwt, httpx; print('backend deps OK')"
```

All Makefile targets invoke `.venv/bin/python`, so keep the virtual environment
at `backend/.venv`. If it already exists and the import check passes, skip this
section.

## 2. Configuration

`app/config.py` reads `os.environ` directly. There is **no `.env` auto-loader**
and no seed script in this backend, so export variables in your shell (or prefix
a command) before starting the server or running Alembic.

| Variable | Default | Purpose |
|---|---|---|
| `IOTPRM_DATABASE_URL` | `sqlite:///data/iot.db` | SQLAlchemy database URL used by the app and Alembic. Relative SQLite paths are resolved from the current directory, so run commands from `backend/`. The SQLite parent directory is created automatically. |
| `IOTPRM_SECRET_KEY` | `dev-secret-change-me-iot-property-risk-42-chars!!` | HS256 secret for user access tokens. Change it outside local development; changing it invalidates existing tokens. |
| `IOTPRM_PUBLIC_URL` | `http://localhost:8000` | Base URL placed in the `qr_url` returned by pair-start. Set it to the address reachable by the mobile device. |
| `IOTPRM_SWEEP_INTERVAL_SECONDS` | `30` | How often the background disconnect sweeper runs. |
| `IOTPRM_TELEMETRY_TIMEOUT_MINUTES` | `5` | Silence window after which an active device is marked `disconnected` and fail-safe risk is applied. |
| `IOTPRM_PAIRING_TOKEN_TTL_SECONDS` | `600` | Pairing-token lifetime (single use, stored hashed). |
| `IOTPRM_SMTP_HOST` | empty | SMTP host. Email notifications are only sent when this is set. |
| `IOTPRM_SMTP_PORT` | `587` | SMTP port (STARTTLS is used). |
| `IOTPRM_SMTP_USER` | empty | SMTP username. |
| `IOTPRM_SMTP_PASSWORD` | empty | SMTP password. |
| `IOTPRM_SMTP_FROM` | `iotprm@example.com` | From address for alert emails. |
| `IOTPRM_TWILIO_ACCOUNT_SID` | empty | Twilio account SID for SMS. |
| `IOTPRM_TWILIO_AUTH_TOKEN` | empty | Twilio auth token. |
| `IOTPRM_TWILIO_FROM` | empty | Twilio sender number. |

Example shell setup:

```bash
export IOTPRM_DATABASE_URL="sqlite:///data/iot.db"
export IOTPRM_SECRET_KEY="replace-with-a-long-random-string"
export IOTPRM_PUBLIC_URL="http://localhost:8000"
```

Notes:

- Notification rows are recorded for every subscribed channel. Email/SMS are
  actually sent only when the corresponding SMTP/Twilio variables are set;
  otherwise the backend records the notification only.
- `IOTPRM_PUBLIC_URL` does not change the address Uvicorn binds to.

## 3. Database and migrations

The default development database is the SQLite file `backend/data/iot.db`.
Alembic reads `IOTPRM_DATABASE_URL` via `migrations/env.py`, so the app and
migrations always use the same database.

Run from `backend/`:

```bash
.venv/bin/alembic upgrade head
.venv/bin/alembic current
.venv/bin/alembic history
```

`alembic current` should report:

```text
0003_alert_armed_mode (head)
```

Revisions:

| Revision | Adds |
|---|---|
| `0001_initial` | All initial tables (`users`, properties, devices, pairing/device tokens, telemetry, alerts, subscriptions, notifications). |
| `0002_system_modes` | `system_modes`, `system_mode_history`, and `telemetry_events.armed_mode`. |
| `0003_alert_armed_mode` | `alerts.armed_mode` (arming mode when the alert was raised). |

Important:

- The server lifespan also calls `init_db()` (`Base.metadata.create_all`) on
  startup. That creates missing tables but **does not alter existing ones**.
  After pulling a schema change, run `alembic upgrade head`.
- Stop the server before migrating the SQLite file.
- To reset a disposable development database (destructive):

```bash
rm -f data/iot.db
.venv/bin/alembic upgrade head
```

## 4. Tests, lint, and import check

```bash
make test     # .venv/bin/python -m pytest -q
make lint     # ruff check app tests simulator
make check    # compileall + import app.main
```

Targeted runs:

```bash
.venv/bin/python -m pytest tests/test_ingest.py -q
.venv/bin/python -m pytest tests/test_simulator.py -q
```

Tests use an in-memory SQLite database and FastAPI's `TestClient`
(`tests/conftest.py`), so no running server or development database is needed.
The simulator tests drive the real pairing/ingest routes against that test app.

## 5. Start the server

```bash
make server
```

That runs:

```bash
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- API base: `http://localhost:8000/api/v1`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI document: `http://localhost:8000/openapi.json`
- WebSocket: `ws://localhost:8000/api/v1/devices/{device_id}/stream?token=<user JWT>`
- Port: **8000** (hard-coded in the Makefile). If you change it, also set
  `IOTPRM_PUBLIC_URL` accordingly and pass `--base-url` to the simulator.
- Startup creates any missing tables and starts the disconnect sweeper using
  `IOTPRM_SWEEP_INTERVAL_SECONDS` / `IOTPRM_TELEMETRY_TIMEOUT_MINUTES`.
- Stop with `Ctrl-C`.

## 6. API and behavior at a glance

### Signals and arming modes

Monitored signals: `smoke_gas`, `flame`, `water_leak`, `motion`. Alerts can also
be raised for `sensor_fault` and `device_disconnected`.

Each property has exactly one mode:

| Mode | Motion behavior | Other signals |
|---|---|---|
| `unarmed` | Motion is recorded but creates **no new alerts**. Existing motion alerts resolve when motion returns to zero. | Smoke/gas, flame, water leak, sensor faults, and disconnects are always monitored. |
| `armed` | A motion rise creates a `notice` alert. | Same as `unarmed`. |
| `armed_away` | Same as `armed`. | Same as `unarmed`. |

Mode endpoints:

- `GET /api/v1/system/modes` — current mode per property (any member).
- `PUT /api/v1/system/modes/{property_id}` `{ "mode": "unarmed" | "armed" | "armed_away" }` — owner/admin.
- `GET /api/v1/system/modes/{property_id}/history` — owner/admin/responder.
- `GET /api/v1/devices/{device_id}/mode` — device-token auth, used by firmware to sync the mode down.

The backend is authoritative for mode changes. Device telemetry still carries
`armed_mode` and is stored on the telemetry row; it only initializes the
property mode if no mode row exists yet, so stale/buffered telemetry cannot
revert a mode chosen in the app.

### Alert thresholds

Risk ladder: `ok < notice < warning < alert < critical`. The `smoke_gas` signal
uses the higher of the smoke and gas levels.

| Signal | `warning` | `alert` | `critical` |
|---|---|---|---|
| Smoke (ppm) | ≥ 301 (clears ≤ 250) | ≥ 701 (clears ≤ 650) | > 1000 (clears ≤ 950) |
| Gas (ppm) | ≥ 11 (clears ≤ 8) | ≥ 31 (clears ≤ 25) | ≥ 61 (clears ≤ 50) |
| Flame | — | — | detected |
| Water leak (0–100) | ≥ 1 (clears at 0) | ≥ 25 (clears ≤ 24) | ≥ 50 (clears ≤ 10) |
| Motion | — | — | — (always `notice` when detected) |

`device.risk_level` is the maximum signal level; `property.risk_level` is the
maximum non-revoked device risk. On disconnect, the sweeper applies fail-safe
levels (`smoke_gas`/`flame` → critical, `water_leak` → warning, `motion` →
notice) and creates a `device_disconnected` warning alert. The next accepted
telemetry returns the device to `active` and resolves that alert.

Sensor faults: a non-empty `faults` list creates a `sensor_fault` notice alert.
When a later telemetry reports an empty (or changed) list, the old alert is
resolved. Alerts record the arming mode at creation and serialize it as
`system_mode`.

Alert lifecycle: `open` → `acknowledged` (via ack) → `resolved` (automatic when
the signal drops, or on device revoke). `GET /api/v1/alerts` supports `status`,
`severity`, `device_id`, `since`, `limit`, and `offset`; responses are
`{items, total, limit, offset}`.

### Roles

| Action | owner | admin | responder | viewer |
|---|---|---|---|---|
| Read devices/status/alerts/events | ✔ | ✔ | ✔ | ✔ |
| Acknowledge alerts | ✔ | ✔ | ✔ | ✘ |
| Pair/claim and revoke devices | ✔ | ✔ | ✘ | ✘ |
| Edit property settings | ✔ | ✔ | ✘ | ✘ |
| Read system modes | ✔ | ✔ | ✔ | ✔ |
| Set system mode | ✔ | ✔ | ✘ | ✘ |
| View mode history | ✔ | ✔ | ✔ | ✘ |

### Pairing and device auth

Pairing is a three-step flow (the simulator automates all of it):

1. `POST /api/v1/devices/{device_id}/pair-start` (unauthenticated, rate-limited
   to 5 requests/min per `device_id`) → `{device_id, token, qr_url, expires_at}`.
   Returns `409` if the device is already active.
2. The mobile app claims the token:
   `POST /api/v1/pair` `{ "token": "pt_..." }` with a user Bearer token. The
   caller must be owner/admin of the target property. The response contains the
   device credential: `{device_id, property_id, device_token}`.
3. The device polls `GET /api/v1/devices/{device_id}/pair-status` with
   `Authorization: Bearer <pairing token>` until it receives
   `{ "status": "active", "device_token": "dt_..." }`.

Pairing tokens are single-use and expire after
`IOTPRM_PAIRING_TOKEN_TTL_SECONDS`. Device tokens (`dt_...`) authenticate
telemetry ingest and the device-mode endpoint. Revoking a device sets it to
`revoked`, invalidates its token, and resolves its open alerts; a revoked device
can be re-paired.

### Telemetry ingest

`POST /api/v1/ingest/telemetry` with `Authorization: Bearer <device token>` and
the SPEC §1 payload:

```json
{
  "device_id": "esp32-a1b2c3d4e5f6",
  "timestamp": "2026-11-20T12:00:00.123Z",
  "sequence": 17,
  "armed_mode": "unarmed",
  "battery_pct": 87,
  "rssi_dbm": -62,
  "device_health": "ok",
  "faults": [],
  "sensors": {
    "smoke_gas": { "smoke_ppm": 412.5, "gas_ppm": 87 },
    "flame": { "detected": false },
    "water_leak": { "detected": false, "level": 0 },
    "motion": { "motion_detected": false, "occupancy": false }
  }
}
```

Responses:

- `{ "accepted": true, "sequence": 17 }`
- `{ "accepted": false, "reason": "stale_sequence", "sequence": 17 }` for a
  duplicate `(device_id, sequence)`.
- `401` for a revoked/invalid device token or a device that is not active.
- `422` for invalid shapes/values (sequence, sensors, health, mode, etc.).

### WebSocket

`WS /api/v1/devices/{device_id}/stream` authenticates with `?token=<user JWT>`
or an `Authorization: Bearer` header. On connect it sends
`{"type":"connected","device_id":...,"sequence":0}`, then pushes
`{"type":"telemetry","payload":{...}}` for new events and
`{"type":"alert","payload":{...}}` for open alerts. It polls the database every
0.5 s.

### Errors

API errors use the SPEC envelope:

```json
{ "error": { "code": "FORBIDDEN", "message": "FORBIDDEN" } }
```

Codes include `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `INVALID`, `CONFLICT`,
`RATE_LIMITED`, `TOO_MANY_REQUESTS`, `TOKEN_INVALID`, `DEVICE_ACTIVE`, and
`PAIRING_UNAVAILABLE`. Validation failures return `422` with an `INVALID` code.

## 7. IoT simulator

The simulator lives in `backend/simulator/` and drives the **real** backend:
it logs in (or registers), runs the real pair-start/claim flow, publishes SPEC
§1 telemetry through `POST /api/v1/ingest/telemetry` with the issued device
token, polls `GET /api/v1/system/modes` each tick, and calls the mode endpoint
when a scenario changes the mode. Alerts therefore appear in the normal alerts
API and in the mobile app.

### Prerequisites

- The backend is running (`make server`) at `http://localhost:8000` unless you
  pass `--base-url`.
- The database is migrated (`alembic upgrade head`).
- `httpx` is installed in `.venv` (it is a runtime dependency).

### Basic run

From `backend/`:

```bash
.venv/bin/python -m simulator.simulate --scenario background --duration 30
```

or through the Makefile:

```bash
make simulate SIM_ARGS="--scenario background --duration 30"
```

By default the simulator:

- logs in as `sim-user@example.com` / `pw123456`, registering the user (with a
  default `Home` property) if it does not exist;
- pairs device `esp32-sim-001` (or resumes with `--token`);
- discovers the device's last telemetry sequence and resumes after it;
- publishes every `--interval` seconds (default 5);
- prints a timeline and, at the end, the open alerts.

To watch the same data in the mobile app, log in as `sim-user@example.com` /
`pw123456`. The simulator's device is paired to that user's property.

### Scenarios

The simulator's calm baseline is smoke 150 ppm, gas 5 ppm, no flame, water level
0, no motion, battery 100, RSSI −50 dBm, health `ok`, no faults.

| `--scenario` | Timeline | Expected alerts |
|---|---|---|
| `none` / `background` | Calm baseline for the whole run. | None. |
| `smoke-spike` | `smoke_ppm = 420` for the first 3 s, then baseline. | `smoke_gas` **warning** (gas stays at 5 ppm). Resolves when smoke drops. |
| `flame` | `flame.detected = true` for the first 3 s. | `flame` **critical**. Resolves when flame clears. |
| `water-leak` | `water_leak.level = 30` (and `detected = true`) for the first 3 s. | `water_leak` **alert** (level 30 is in the 25–49 band). Resolves at level 0. |
| `motion-unarmed` | Motion on for 0–4 s while unarmed; mode set to `armed` at 5–6 s; motion off 6–9 s; motion on from 10 s; mode set to `unarmed` at 13.5–14.5 s. | No alert during the unarmed motion. A `motion` **notice** opens after the 10 s rise (while armed). It stays open because motion remains on when the run ends. |
| `motion-armed` | Forces `armed` if the mode is different; motion on 0–4 s, off 4–7 s, on from 7 s. | Two `motion` **notice** alerts over time (the second is open at the end). |
| `fault-offline` | `faults = ["simulated_sensor_fault"]` and `device_health = "degraded"` for the first 3 s, then clears. | `sensor_fault` **notice**; resolves when the faults list clears. |
| `recovery` | For the first 3 s: smoke 420, gas 60, flame detected, water level 30, motion detected; then baseline. | `smoke_gas` **alert** (gas 60 dominates smoke 420 warning), `flame` **critical**, `water_leak` **alert**, and `motion` **notice** (motion is gated by the current mode). All resolve after the 3 s recovery. |
| `all` | Fixed stages, back to back: `background` 2 s → `smoke-spike` 4 s → `flame` 3 s → `water-leak` 3 s → `motion-armed` 4 s → `motion-unarmed` 21 s → `fault-offline` 4 s → `recovery` 4 s → `background` 2 s. | Runs the whole demo; `--duration` is ignored for `all`. |

### Demo recipes for each requested case

Use `--interval 1` for short scenarios: with the default 5 s interval, a 3 s
pulse is sampled once and resolved by the next tick. A short `--duration` (2 s)
ends the run while alerts are still open; a longer duration shows recovery.

| Goal | Command (from `backend/`) | Notes |
|---|---|---|
| Normal operation | `.venv/bin/python -m simulator.simulate --scenario background --duration 30` | No alerts; useful for live readings/status. |
| Unarmed motion gating | `.venv/bin/python -m simulator.simulate --scenario motion-unarmed --interval 1 --duration 21` | No motion alert while unarmed; the scenario arms at 5 s, raises motion at 10 s, and disarms at 13.5 s. |
| Armed motion | `.venv/bin/python -m simulator.simulate --scenario motion-armed --initial-mode armed --interval 1 --duration 12` | Motion notices; the second alert is open at the end. |
| Armed away motion | `.venv/bin/python -m simulator.simulate --scenario recovery --initial-mode armed_away --interval 1 --duration 2` | `recovery` raises motion (and all other sensors) without changing the mode, so the motion notice is created in `armed_away`. Use `--duration 10` to watch it resolve. |
| Smoke | `.venv/bin/python -m simulator.simulate --scenario smoke-spike --interval 1 --duration 2` | `smoke_gas` warning. Use `--duration 10` to see it resolve. |
| Gas | `.venv/bin/python -m simulator.simulate --scenario recovery --interval 1 --duration 2` | Gas is 60 ppm in `recovery` → `smoke_gas` **alert** severity (there is no dedicated gas-only stage). |
| Flame | `.venv/bin/python -m simulator.simulate --scenario flame --interval 1 --duration 2` | `flame` critical. |
| Water leak | `.venv/bin/python -m simulator.simulate --scenario water-leak --interval 1 --duration 2` | `water_leak` alert at level 30. |
| Sensor fault | `.venv/bin/python -m simulator.simulate --scenario fault-offline --interval 1 --duration 2` | `sensor_fault` notice; use `--duration 10` to see the faults clear and the alert resolve. |
| Recovery | `.venv/bin/python -m simulator.simulate --scenario recovery --interval 1 --duration 10` | All signals elevated for 3 s, then back to baseline; alerts resolve. |
| Full demo | `.venv/bin/python -m simulator.simulate --scenario all` | Runs the fixed stage list above. |

All of the above also work through `make simulate SIM_ARGS="..."`, for example:

```bash
make simulate SIM_ARGS="--scenario motion-armed --initial-mode armed --interval 1 --duration 12"
```

### Options

| Option | Default | Meaning |
|---|---|---|
| `--base-url` | `http://localhost:8000` | Backend base URL. |
| `--device-id` | `esp32-sim-001` | Simulated device id. |
| `--user-email` | `sim-user@example.com` | Login email; registration is attempted if login fails. |
| `--user-password` | `pw123456` | Login/registration password. |
| `--user-name` | `Sim User` | Name used only when registering. |
| `--token` | none | Use an existing device token and skip pairing. |
| `--property-id` | none | Override the property. With `--token`, it is auto-discovered from `GET /api/v1/devices` when possible and required otherwise. |
| `--reset` | off | If pair-start returns `409` (device already active), revoke the device via `DELETE /api/v1/devices/{id}` and re-pair it. |
| `--initial-mode` | none | Set `unarmed`, `armed`, or `armed_away` after pairing, before the run. `motion-armed` may force `armed` on its first tick. |
| `--scenario` | `all` | One of the scenarios above. |
| `--duration` | `60` | Seconds to run for a single scenario; ignored for `all`. Must be ≥ 0. |
| `--interval` | `5` | Seconds between telemetry publishes. Must be > 0. Use `1` for short pulses. |
| `--start-sequence` | `0` | First sequence to publish. The simulator still discovers the device's last sequence and resumes after it. |
| `--quiet` | off | Suppress the timeline log; the final open-alert line is still printed. |

### Reruns, reset, and sequences

- The first run pairs `esp32-sim-001`. A second run without `--reset` stops
  with a message that the device is already active.
- `--reset` revokes and re-pairs the simulated device (which also resolves its
  open alerts). Alternatively, pass a different `--device-id`.
- Telemetry is deduplicated by `(device_id, sequence)`. The simulator reads the
  last sequence from `GET /api/v1/devices/{device_id}/status` and resumes after
  it, so reruns do not produce `stale_sequence` responses. `--start-sequence`
  can set a higher starting point.
- With `--token`, pairing is skipped; the token must belong to an active device
  and `--property-id` may be required.

### Troubleshooting the simulator

| Symptom | Cause / fix |
|---|---|
| `Connection refused` | The backend is not running, or `--base-url` is wrong. Start it with `make server`. |
| `device ... is already active` | Rerun with `--reset`, or use another `--device-id`. |
| `device token rejected` | The device was revoked or the token is stale. Re-pair with `--reset`, or pass a current `--token`. |
| `could not login or register user` | The email exists with a different password, or registration was rejected. Pass the matching `--user-password` or use a new `--user-email`. |
| No alerts visible | Motion is gated while unarmed, the 3 s pulse was missed at a 5 s interval, or the alert already resolved. Use `--interval 1 --duration 2` and inspect immediately. |
| `pair-start failed: ...` | Pairing may be rate-limited (5/min per device id) or the device is active. Wait a minute or use `--reset`. |
| `stale_sequence` in responses | Should be handled automatically; pass `--start-sequence` above the last known sequence if needed. |
| Database column/schema errors | Run `.venv/bin/alembic upgrade head` from `backend/` (stop the server first for SQLite). |
| Port 8000 already in use | Stop the other process; the Makefile server target is hard-coded to 8000. |

## 8. Layout

```text
backend/
├── app/
│   ├── api/             HTTP routes (auth/users, devices, ingest, alerts, pairing, system modes) + WebSocket
│   ├── alerts.py        Alert transitions and dispatch
│   ├── config.py        Environment configuration
│   ├── database.py      Engine/session + startup create_all
│   ├── main.py          FastAPI app, error envelope, sweeper lifespan
│   ├── models.py        SQLAlchemy models and system-mode helpers
│   ├── notifications.py Optional email/SMS dispatch
│   ├── pairing.py       Pairing-token and device-claim logic
│   ├── risk.py          Risk recomputation, fail-safe, stale-device sweep
│   ├── security.py      Password/JWT/token helpers and role checks
│   └── thresholds.py    Signal levels and risk aggregation
├── migrations/          Alembic revisions 0001–0003
├── simulator/           HTTP device simulator and CLI
├── tests/               Pytest suite (in-memory SQLite)
├── Makefile             test / lint / check / server / simulate
├── alembic.ini
└── pyproject.toml
```

For the full JSON schemas, thresholds, role matrix, and edge-case rules, see
[`docs/SPEC.md`](../docs/SPEC.md). For simulator-specific notes, see
[`simulator/README.md`](simulator/README.md).
