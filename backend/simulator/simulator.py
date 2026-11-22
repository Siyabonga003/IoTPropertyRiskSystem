"""IoT device simulator — drives the real ingest pipeline with simulated readings.

Registers (or reuses) a simulated device and continuously publishes telemetry
exactly as an ESP32 firmware would: continuous background readings for all four
sensors (smoke/gas, flame, water leak, motion) plus triggerable scenario
timelines, with the property's synced arming state (SPEC §2 — system arming modes).

The simulator talks to a running backend over HTTP: it uses the real pairing
flow (POST /api/v1/devices/{id}/pair-start + POST /api/v1/pair), the real
device-token auth for ingest (POST /api/v1/ingest/telemetry), and the real
system-mode endpoints (GET/PUT /api/v1/system/modes/...).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import httpx

from app.models import ARMED, UNARMED

# Background ("normal") readings — realistic calm values (all OK per §2 thresholds).
DEFAULT_READINGS: dict[str, Any] = {
    "smoke_ppm": 150.0,
    "gas_ppm": 5.0,
    "flame_detected": False,
    "water_detected": False,
    "water_level": 0,
    "motion_detected": False,
    "occupancy": False,
    "battery_pct": 100,
    "rssi_dbm": -50,
    "device_health": "ok",
    "faults": [],
}

SCENARIOS = (
    "none",
    "background",
    "smoke-spike",
    "flame",
    "water-leak",
    "motion-unarmed",
    "motion-armed",
    "fault-offline",
    "recovery",
    "all",
)

# Stages for scenario "all": (scenario, duration_seconds).
ALL_STAGES = (
    ("background", 2.0),
    ("smoke-spike", 4.0),
    ("flame", 3.0),
    ("water-leak", 3.0),
    ("motion-armed", 4.0),
    ("motion-unarmed", 21.0),
    ("fault-offline", 4.0),
    ("recovery", 4.0),
    ("background", 2.0),
)


class Simulator:
    """Publishes simulated telemetry through the real backend ingest pipeline."""

    def __init__(
        self,
        client,
        *,
        device_id: str,
        device_token: str | None = None,
        property_id: str | None = None,
        user_token: str | None = None,
        interval: float = 5.0,
        verbose: bool = True,
        sequence: int = 0,
    ):
        self.client = client  # httpx.Client (or TestClient)
        self.device_id = device_id
        self.device_token = device_token
        self.property_id = property_id
        self.user_token = user_token
        self.interval = interval
        self.verbose = verbose
        self.sequence = sequence
        self.mode = UNARMED
        self._last_log = 0.0
        self._mode_warning = False

    # -- logging --------------------------------------------------------------

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[sim] {msg}", flush=True)

    # -- http helpers ------------------------------------------------------------

    def _headers(self, token: str | None) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"} if token else {}

    # -- mode sync (device/user) --------------------------------------------------

    def get_mode(self) -> str:
        """Read the current mode for our property (sync-down).

        A transient backend error must not kill a demo; keep the last known mode
        and warn once.
        """
        if not self.user_token:
            return self.mode
        try:
            r = self.client.get("/api/v1/system/modes", headers=self._headers(self.user_token))
            r.raise_for_status()
            for item in r.json():
                if self.property_id is None or item.get("property_id") == self.property_id:
                    self.mode = item.get("mode") or self.mode
            self._mode_warning = False
        except httpx.HTTPError as exc:
            if not self._mode_warning:
                self._log(f"mode sync unavailable ({exc}); keeping {self.mode}")
                self._mode_warning = True
        return self.mode

    def set_mode(self, mode: str) -> None:
        """Set the property mode via the real API (owner/admin)."""
        if self.property_id is None or not self.user_token:
            self.mode = mode
            return
        try:
            r = self.client.put(
                f"/api/v1/system/modes/{self.property_id}",
                json={"mode": mode},
                headers=self._headers(self.user_token),
            )
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"could not set mode {mode!r}: {exc}") from exc
        self.mode = mode
        self._log(f"mode -> {mode}")

    def discover_sequence(self) -> int:
        """Start after the device's last known sequence so reruns are not stale."""
        if not self.user_token:
            return self.sequence
        try:
            r = self.client.get(
                f"/api/v1/devices/{self.device_id}/status",
                headers=self._headers(self.user_token),
            )
            r.raise_for_status()
            last = (r.json() or {}).get("last_telemetry") or {}
            seq = last.get("sequence")
            if isinstance(seq, int) and seq > self.sequence:
                self.sequence = seq
                self._log(f"resuming after sequence {seq}")
        except httpx.HTTPError as exc:
            self._log(f"could not read last sequence ({exc}); starting at {self.sequence}")
        return self.sequence

    # -- telemetry -----------------------------------------------------------------

    def build_telemetry(self, overrides: dict[str, Any]) -> dict[str, Any]:
        """Build a firmware-style telemetry payload (SPEC §1) with scenario overrides."""
        self.sequence += 1
        r = dict(DEFAULT_READINGS)
        r.update({k: v for k, v in overrides.items() if k in DEFAULT_READINGS})
        r["water_detected"] = r["water_detected"] or r["water_level"] > 0
        return {
            "device_id": self.device_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "sequence": self.sequence,
            "battery_pct": r.get("battery_pct", 100),
            "rssi_dbm": r.get("rssi_dbm", -50),
            "device_health": r.get("device_health", "ok"),
            "faults": r.get("faults", []),
            "armed_mode": self.mode,
            "sensors": {
                "smoke_gas": {"smoke_ppm": r["smoke_ppm"], "gas_ppm": r["gas_ppm"]},
                "flame": {"detected": r["flame_detected"]},
                "water_leak": {"detected": r["water_detected"], "level": r["water_level"]},
                "motion": {"motion_detected": r["motion_detected"], "occupancy": r["occupancy"]},
            },
        }

    def ingest(self, telemetry: dict[str, Any]) -> Any:
        """Publish telemetry via the real ingest route (device-token auth)."""
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                r = self.client.post(
                    "/api/v1/ingest/telemetry",
                    json=telemetry,
                    headers=self._headers(self.device_token),
                )
                if r.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"ingest returned {r.status_code}", request=r.request, response=r
                    )
                if r.status_code == 401:
                    raise RuntimeError(
                        "device token rejected (is the device revoked? re-pair or use --reset)"
                    )
                r.raise_for_status()
                return r.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.25 * (attempt + 1))
        raise RuntimeError(f"ingest failed after retries: {last_error}")

    # -- scenarios ---------------------------------------------------------------------

    def _plan(self, scenario: str, t: float, mode: str):
        """Return (overrides, new_mode) for the scenario at elapsed time t."""
        ov: dict[str, Any] = {}
        new_mode = None
        if scenario in (None, "none", "background"):
            pass
        elif scenario == "smoke-spike":
            if 0 <= t < 3:
                ov["smoke_ppm"] = 420.0
        elif scenario == "flame":
            if 0 <= t < 3:
                ov["flame_detected"] = True
        elif scenario == "water-leak":
            if 0 <= t < 3:
                ov["water_level"] = 30
        elif scenario == "fault-offline":
            if 0 <= t < 3:
                ov["faults"] = ["simulated_sensor_fault"]
                ov["device_health"] = "degraded"
        elif scenario == "recovery":
            if 0 <= t < 3:
                ov.update(smoke_ppm=420.0, gas_ppm=60.0, flame_detected=True, water_level=30, motion_detected=True)
        elif scenario == "motion-unarmed":
            if 0 <= t < 4:
                ov["motion_detected"] = True  # while unarmed: no alerts
            if 6 <= t < 9:
                ov["motion_detected"] = False
            if 10 <= t:
                ov["motion_detected"] = True  # rise while armed: alert, stays open to the end
            if 5 <= t < 6:
                new_mode = ARMED
            if 13.5 <= t < 14.5:
                new_mode = UNARMED
        elif scenario == "motion-armed":
            if 0 <= t < 4:
                ov["motion_detected"] = True  # alert #1
            if 7 <= t:
                ov["motion_detected"] = True  # rise again after drop: alert #2 (open)
            if mode != ARMED:
                new_mode = ARMED
        else:
            raise ValueError(f"unknown scenario: {scenario}")
        return ov, new_mode

    # -- main loop ---------------------------------------------------------------------

    def run(self, scenario: str, duration: float, interval: float | None = None, on_tick=None) -> None:
        """Run the simulator for `duration` seconds with the given scenario.

        scenario "all" runs ALL_STAGES back to back.
        """
        if scenario == "all":
            for name, dur in ALL_STAGES:
                self.run(name, dur, interval=interval, on_tick=on_tick)
            return
        if interval is None:
            interval = self.interval
        start = time.monotonic()
        errors = 0
        while (time.monotonic() - start) < duration:
            t = time.monotonic() - start
            try:
                mode = self.get_mode()
                overrides, new_mode = self._plan(scenario, t, mode)
                if new_mode is not None and new_mode != self.mode:
                    self.set_mode(new_mode)
                telemetry = self.build_telemetry(overrides)
                self.ingest(telemetry)
                errors = 0
            except (RuntimeError, httpx.HTTPError) as exc:
                errors += 1
                self._log(f"t={t:6.1f}s telemetry error ({errors}/5): {exc}")
                if errors >= 5:
                    raise
                telemetry = None
            if telemetry is not None and on_tick is not None:
                on_tick(self, t)
            if telemetry is not None and self.verbose and (t - self._last_log) >= 1.0:
                s = telemetry["sensors"]
                self._last_log = t
                self._log(
                    f"t={t:6.1f}s seq={self.sequence:4d} "
                    f"smoke={s['smoke_gas']['smoke_ppm']:7.1f} gas={s['smoke_gas']['gas_ppm']:5.1f} "
                    f"flame={'on' if s['flame']['detected'] else 'off'} "
                    f"water={s['water_leak']['level']:3d} "
                    f"motion={'on' if s['motion']['motion_detected'] else 'off'} mode={self.mode}"
                )
            remaining = duration - (time.monotonic() - start)
            if remaining > 0:
                time.sleep(min(interval, remaining))
