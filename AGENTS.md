# Project Rules: IoT Property Risk Monitoring System

## Architecture & Layout
- `firmware/` — ESP32 firmware (PlatformIO) reading smoke/gas and flame sensors, publishing telemetry/alerts, and supporting device pairing.
- `backend/` — API server, database schema/migrations, multi-tenant role-based access control, QR/token pairing, and alert dispatch.
- `mobile/` — Flutter app for device pairing, live sensor status, and risk alerts.
- `docs/SPEC.md` — Source of truth for JSON payload schemas, MQTT topics or HTTP routes, and auth/pairing flows.

## Verification Commands
- Firmware: `pio run` inside `firmware/` after any C/C++ or `platformio.ini` edit.
- Backend: Run tests/lint/server check inside `backend/` after route or schema changes.
- Mobile: Run `flutter analyze` inside `mobile/` after Dart changes.

