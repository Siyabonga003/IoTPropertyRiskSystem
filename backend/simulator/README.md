# Device simulator (backend)

Drives the real ingest pipeline (`POST /api/v1/ingest/telemetry`) with simulated
ESP32-style readings, so you can demo the system without hardware. All telemetry
flows through the real device-token auth, alert pipeline, and arming-state sync.

## Setup

Requires the project venv (`httpx` is a direct dependency).

```bash
cd backend
```

## Run

From `backend/`:

```bash
.venv/bin/python -m simulator.simulate --scenario all --duration 60
```

(or `make simulate SIM_ARGS="--scenario smoke-spike"`.)

Requires the backend running at `http://localhost:8000` (`make server`).

## Scenarios

| scenario | what happens |
|---|---|
| `background` | Continuous normal readings for all four sensors + metadata |
| `smoke-spike` | smoke_ppm → 420 for ~3 s (warning alert), then recovers |
| `flame` | Flame detected for ~3 s → critical alert, then recovers |
| `water-leak` | water_level = 30 for ~3 s (warning alert), then recovers |
| `motion-unarmed` | Motion while unarmed → **no alerts**; arms; motion → alert; disarms → no new alerts |
| `motion-armed` | Armed motion → alert(s) |
| `fault-offline` | `faults=["simulated_sensor_fault"]` + `device_health="degraded"` for ~3 s |
| `recovery` | All sensors elevated, then back to normal |
| `all` | background → smoke-spike → flame → water-leak → motion-armed → motion-unarmed → fault-offline → recovery |

Notes:
- The simulator polls `GET /api/v1/system/modes` each interval and includes
  `armed_mode` in every telemetry payload — so flipping the mode in the Flutter
  app is immediately reflected in the readings stream.
- Telemetry payloads follow SPEC §1 exactly (four sensors + metadata).

## Options

- `--base-url` (default `http://localhost:8000`) — backend base URL.
- `--device-id` (default `esp32-sim-001`) — simulated device_id.
- `--user-email` / `--user-password` — user credentials (login, or register if
  none exists — `--user-name` sets the name when registering).
- `--token` — use an existing device token; skips the pairing flow.
- `--property-id` — override the property (auto-detected after pairing; required
  with `--token` if not discoverable).
- `--reset` — revoke an already-active simulated device, then re-pair it. Handy
  when rerunning a demo with the default device id.
- `--initial-mode` — set the mode after pairing (`unarmed`, `armed`, `armed_away`).
- `--scenario` — one of the scenarios above (default `all`).
- `--duration` — seconds per scenario; ignored for `all` (stage durations are fixed).
- `--interval` — publish cadence, seconds (default `5`).
- `--start-sequence` — first telemetry sequence (default `0`); the simulator also
  discovers the device's last sequence and resumes after it, so reruns are not
  rejected as `stale_sequence`.
- `--quiet` — suppress the timeline log.

## Quick smoke test

```bash
.venv/bin/python -m pytest tests/test_simulator.py -q
```
