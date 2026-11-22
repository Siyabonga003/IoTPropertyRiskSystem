# IoT Property Risk Monitoring System — SPEC.md (Draft v0.3)

Four monitored signal types: **smoke/gas**, **flame**, **water leak**, and **motion**.

```
ESP32 firmware ──(MQTT, or HTTP: POST /api/v1/ingest/telemetry)──▶ Backend ──▶ DB ─┬─▶ Mobile: /status polling + WS events
                                                                                 ├─▶ Mobile: alert list
                                                                                 └─▶ Alert dispatch (push/email/SMS)
```

## 1. Telemetry JSON schema (firmware → backend)

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
    "smoke_gas":    { "smoke_ppm": 412.5, "gas_ppm": 87 },
    "flame":        { "detected": false },
    "water_leak":   { "detected": false, "level": 0 },
    "motion":       { "motion_detected": false, "occupancy": false }
  }
}
```

| Field | Notes |
|---|---|
| `device_id` | Stable unique id (e.g. ESP32 MAC). Backend is authoritative after pairing. |
| `timestamp` | ISO 8601 UTC from device clock. |
| `sequence` | Monotonic per device from 1 — dedup key `(device_id, sequence)`. |
| `armed_mode` | Optional; the property's current system arming mode: `unarmed`, `armed`, or `armed_away`. |
| `battery_pct` | Optional; reported on change/heartbeat. |
| `rssi_dbm` | Optional, meaningful on MQTT publish. |
| `device_health` | `ok \| degraded \| fault \| disconnected`. |
| `faults` | Sensor fault strings, e.g. `["heater_timeout", "sensor_disconnected"]`. |
| `sensors.smoke_gas.smoke_ppm` / `.gas_ppm` | Numbers, analog sensor readings. |
| `sensors.flame.detected` | Digital flame sensor state (bool). |
| `sensors.water_leak.detected` | Digital leak sensor state (bool). |
| `sensors.water_leak.level` | Int 0–100; 0 = no detection. |
| `sensors.motion.motion_detected` | Transient motion event (debounced in firmware). |
| `sensors.motion.occupancy` | True while someone is in range; expires after firmware-side idle timeout (draft: 60 s). |

### System arming modes

Per property, the system is in exactly one mode at a time (§4, system mode endpoints):

| Mode | Motion alerts | Other signals |
|---|---|---|
| `unarmed` | No new motion alerts; open motion alerts resolve when motion returns to zero. Motion level is still reported. | `smoke_gas`, `flame`, `water_leak`, `sensor_fault`, `device_disconnected` monitored as usual |
| `armed` | Motion creates notice alerts (§2.6) | Same as `unarmed` |
| `armed_away` | Motion creates notice alerts (§2.6) | Same as `unarmed` |

Rules:
- Devices report `armed_mode` in every telemetry (§1); the backend stores it on `telemetry_events.armed_mode`. If a property has no `system_modes` row yet, the reported value initializes it; afterwards the backend is authoritative for changes (`PUT` below).
- `PUT /api/v1/system/modes/{property_id}` changes the mode (owner/admin) and appends `system_mode_history` audit rows. Devices poll `GET /api/v1/devices/{device_id}/mode` and include the result in their next telemetry.
- When unarmed, motion never creates new alerts. When armed or armed_away, motion creates notice alerts per §2.6. Smoke/gas, flame, water leak, sensor faults, and disconnects are always monitored.
- Each alert records the arming mode in force when it was raised (serialized as `system_mode`).

**Backend-computed derived state** (stored in DB, not sent by firmware):

| Field | Definition |
|---|---|
| `device.sensor_levels` | Per-signal current level: `smoke_gas`, `flame`, `water_leak`, `motion`. |
| `device.risk_level` | `max(sensor_levels.values())`. |
| `property.risk_level` | `max(device.risk_level for device in property)`. |
| `device.status` | `pairing \| active \| revoked \| disconnected`. |

## 2. Alert thresholds & risk states (draft values marked)

Risk levels: `ok < notice < warning < alert < critical`. (Motion risk is `notice` only; other sensors use the full ladder.)

### Smoke (ppm) — enter level when reading ≥; clears when drops to:
| Level | Enter | Clear |
|---|---|---|
| warning | ≥ 301 | ≤ 250 |
| alert | ≥ 701 | ≤ 650 |
| critical | > 1000 | ≤ 950 |

### Gas (ppm) — [DRAFT: assumes CO/combustible-gas sensor]
| Level | Enter | Clear |
|---|---|---|
| warning | ≥ 11 | ≤ 8 |
| alert | ≥ 31 | ≤ 25 |
| critical | ≥ 61 | ≤ 50 |

### Flame — digital
| Level | Enter | Clear |
|---|---|---|
| critical | `detected == true` | `detected == false` |

### Water leak
| Level | Enter | Clear |
|---|---|---|
| warning | `level ≥ 1` (any detection) | `level == 0` |
| alert | `level ≥ 25` (medium+) | `level ≤ 24` |
| critical | `level ≥ 50` (severe/flooding) | `level ≤ 10` |
[DRAFT level scale: 0 = none, 1–24 low, 25–49 medium, 50+ severe]

### Motion
| Level | Enter | Clear |
|---|---|---|
| notice | `motion_detected == true` | idle (no motion in window) |

### Fail-safe on sensor disconnect (backend)
If no telemetry for `telemetry_timeout` (5 min, draft): `device.status = "disconnected"` + `device_disconnected` alert (severity warning). Device-risk contribution per type (conservative): `smoke_gas → critical`, `flame → critical`, `water_leak → warning`, `motion → notice`.

### Sensor faults
When telemetry includes a non-empty `faults` list, the backend creates a `sensor_fault` alert (signal `sensor_fault`, severity `notice`, status open) and records the faults on the device. The open fault alert resolves when a later telemetry reports an empty `faults` list (or a changed list, which replaces the alert notes). Fault and disconnect alerts carry the property's arming mode at creation time.

## 3. Provisioning / pairing flow (QR + token)

Token formats (draft): pairing `pt_` + 12 random bytes hex (96-bit); device `dt_` + 16 random bytes hex. Pairing token TTL 600 s; single-use; stored as SHA-256 hash only.

1. **Device** enters pairing mode: `POST /api/v1/devices/{device_id}/pair-start` (rate-limited, unauthenticated) → `{ device_id, token, qr_url, expires_at }`. `qr_url` = `https://{host}/pair?token={token}`.
2. **Device** polls `GET /api/v1/devices/{device_id}/pair-status` (Bearer pairing token) every ~5 s → `{ status: "pairing" }`.
3. **Mobile** scans QR → `POST /api/v1/pair` (`{ token }`, Bearer user token).
4. **Server** validates token (exists, unexpired, unused, device pairing, user is owner/admin of the target property) → creates device (`status=active`, `property_id`, `paired_at`), issues `device_token`, returns `{ device_id, property_id, device_token }`. Token consumed.
5. **Device** polls `pair-status` → `{ status: "active", device_token }` → starts publishing telemetry (MQTT or `POST /api/v1/ingest/telemetry`).
6. **Revoke**: `DELETE /api/v1/devices/{device_id}` (owner/admin) → status `revoked`; ingest → `401`.

### Roles & access matrix (multi-tenant)

All endpoints scoped to caller's properties (draft: 1 per user; schema allows many).

| Action | owner | admin | responder | viewer |
|---|---|---|---|---|
| List/read devices, status, alerts, events | ✔ | ✔ | ✔ | ✔ |
| Acknowledge alerts | ✔ | ✔ | ✔ | ✘ |
| Ingest telemetry (device token) | ✔ | ✔ | ✘ | ✘ |
| Pair/claim devices | ✔ | ✔ | ✘ | ✘ |
| Revoke devices | ✔ | ✔ | ✘ | ✘ |
| Edit property settings | ✔ | ✔ | ✘ | ✘ |
| Read system modes | ✔ | ✔ | ✔ | ✔ |
| Set system mode | ✔ | ✔ | ✘ | ✘ |
| View mode history | ✔ | ✔ | ✔ | ✘ |

## 4. Transport & API contracts

### MQTT (optional transport)
- `iot/telemetry/{device_id}` — firmware publishes telemetry JSON (§1).
- Backend polls/aggregates from MQTT or uses HTTP ingest.

### HTTP REST (base `/api/v1`)

**Auth & users**
- `POST /api/v1/auth/login` `{email, password}` → `{access_token, token_type: "bearer"}`.
- `POST /api/v1/users` register `{name, email, password}` → creates user + default property ("Home") + membership (owner) → `{access_token, user, property}`.
- `GET /api/v1/me` → `{id, name, email, phone, created_at, properties: [{id, name, risk_level, role}]}`.
- `GET /api/v1/properties/{id}` → `{id, name, risk_level}`.

**Devices**
- `GET /api/v1/devices` — property-scoped list.
- `GET /api/v1/devices/{device_id}` — detail (`device_id, property_id, name, firmware_version, status, paired_at, last_seen_at, risk_level, sensor_levels, last_* readings, battery_pct, rssi_dbm, device_health, faults, system_mode`).
- `GET /api/v1/devices/{device_id}/status` — latest telemetry + `property_risk_level` + `last_telemetry`.
- `GET /api/v1/devices/{device_id}/events?cursor=` — telemetry events with `sequence > cursor` (limit 100).
- `DELETE /api/v1/devices/{device_id}` — revoke (owner/admin).
- `POST /api/v1/devices/{device_id}/pair-start` — begin pairing (§3).
- `GET /api/v1/devices/{device_id}/pair-status` — pairing status (Bearer pairing token).
- `POST /api/v1/pair` — mobile claim (§3).

**Telemetry ingest (firmware)**
- `POST /api/v1/ingest/telemetry` — Bearer device token; body = telemetry JSON (§1) → `{accepted: true, sequence}` or `{accepted: false, reason: "stale_sequence"}`.

**Alerts**
- `GET /api/v1/alerts?status=&severity=&device_id=&since=` — property-scoped, paginated (`limit`, `offset`); each item includes `system_mode` (arming mode when the alert was raised).
- `GET /api/v1/alerts/{id}`.
- `POST /api/v1/alerts/{id}/ack` — responder/admin/owner; sets acknowledged.

**System modes**
- `GET /api/v1/system/modes` — current mode per property (any member).
- `PUT /api/v1/system/modes/{property_id}` `{mode}` — set mode (owner/admin); `mode` is one of `unarmed`/`armed`/`armed_away`; returns updated mode.
- `GET /api/v1/system/modes/{property_id}/history` — mode change history, newest first (owner/admin/responder).
- `GET /api/v1/devices/{device_id}/mode` — device-token auth; current mode (firmware sync-down).

**Notification subscriptions**
- `GET /api/v1/alert_subscriptions` → `[{id, property_id, channels}]`.
- `PUT /api/v1/alert_subscriptions/{property_id}` `{channels: ["push", "email", "sms"]}`.

**Conventions**: JSON in/out; ISO 8601 UTC timestamps; prefixed IDs (`dev_`, `prp_`, `usr_`, `alr_`, `ntf_`, `dt_`, `pt_`); errors `{error: {code, message}}` with codes: `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `INVALID`, `CONFLICT`, `RATE_LIMITED`, `TOO_MANY_REQUESTS`, `TOKEN_INVALID`, `DEVICE_ACTIVE`, `PAIRING_UNAVAILABLE` (draft).

### WebSockets
- `WS /api/v1/devices/{device_id}/stream` — user auth via `?token=` or `Authorization` header; pushes `{"type": "telemetry", "payload": {...}}` and `{"type": "alert", "payload": {...}}`; sends `{"type": "connected", "device_id": ..., "sequence": 0}` on connect; polls DB every 0.5 s.

## 5. Database tables (entities)

| Table | Key columns |
|---|---|
| `users` | id, name, email (unique), password_hash, phone, created_at |
| `properties` | id, name, risk_level |
| `property_members` | user_id, property_id, role (owner/admin/responder/viewer), joined_at — unique(user_id, property_id) |
| `devices` | device_id (PK), property_id FK, name, firmware_version, status, paired_at, last_seen_at, risk_level, sensor_levels (JSON), last_smoke_ppm, last_gas_ppm, last_flame_detected, last_water_level, last_motion_detected, last_occupancy, battery_pct, rssi_dbm, device_health, faults (JSON), created_at, updated_at |
| `device_tokens` | id, device_id (FK), token_hash (unique), revoked_at, issued_at |
| `pairing_tokens` | id, device_id (FK), token_hash (unique), qr_url, expires_at, consumed_at, device_token (nullable), created_at |
| `telemetry_events` | id, device_id (FK), sequence, property_id FK, received_at, timestamp (device clock), smoke_ppm, gas_ppm, flame_detected, water_level, motion_detected, occupancy, battery_pct, rssi_dbm, device_health, device_risk, armed_mode, faults (JSON) — UNIQUE(device_id, sequence) |
  - `system_modes` | property_id (PK, FK properties), mode, updated_at, updated_by
  - `system_mode_history` | id, property_id FK, mode, changed_by, changed_at, reason
| `alerts` | id, property_id FK, device_id FK, signal (smoke_gas/flame/water_leak/motion/device_disconnected/sensor_fault), severity, status (open/acknowledged/resolved), notes, armed_mode (mode at creation), first_seen_at, last_seen_at, acknowledged_at, resolved_at |
| `alert_notifications` | id, alert_id FK, channel (push/email/sms), status, sent_at, error? |
| `alert_subscriptions` | id, property_id FK, user_id FK, channels (JSON, default ["push"]) — unique(property_id, user_id) |

## 6. Key failure / edge cases

1. **Offline buffering (firmware)**: buffer last ~64 telemetry in flash/RAM on publish failure; retry on reconnect; backend dedups by sequence (`stale_sequence` → already-known).
2. **Duplicate readings**: dedup on `(device_id, sequence)`; idempotent ingest (`accepted: false`).
3. **Sensor faults**: non-empty `faults` in telemetry → `sensor_fault` alerts; faults recorded on device.
4. **Disconnect**: background sweeper marks devices disconnected after `telemetry_timeout`; applies fail-safe risks; creates `device_disconnected` alerts. The next accepted telemetry returns the device to `active` and resolves the open disconnect alert.
5. **Invalid tokens**: pairing token invalid (not found / consumed / expired / device not pairing) → `401 UNAUTHORIZED`; revoked device → `401 UNAUTHORIZED`; device token revoked → `401 UNAUTHORIZED`; pair/claim endpoints rate-limited (draft: 5/min per device_id/token + IP).
6. **Motion debounce**: firmware debounces transient motion; `occupancy` expires after idle window; no risk escalation from motion.
7. **Water leak**: no special edge cases; missing sensor → risk `ok`.
