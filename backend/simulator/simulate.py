"""Device simulator CLI — see README.md in this directory."""

from __future__ import annotations

import argparse

import httpx

from app.models import ARMED, ARMED_AWAY, UNARMED
from simulator.simulator import SCENARIOS, Simulator


def _error_text(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}"
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or body)
        return str(body.get("detail") or body)
    return str(body)


def _login(client: httpx.Client, email: str, password: str) -> str | None:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return r.json().get("access_token") if r.status_code == 200 else None


def _register(client: httpx.Client, name: str, email: str, password: str) -> str | None:
    r = client.post("/api/v1/users", json={"name": name, "email": email, "password": password})
    return r.json().get("access_token") if r.status_code == 200 else None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Simulate an ESP32 device against the IoT Property Risk backend.")
    p.add_argument("--base-url", default="http://localhost:8000", help="backend base URL (default: http://localhost:8000)")
    p.add_argument("--device-id", default="esp32-sim-001", help="simulated device_id")
    p.add_argument("--user-email", default="sim-user@example.com")
    p.add_argument("--user-password", default="pw123456")
    p.add_argument("--user-name", default="Sim User")
    p.add_argument("--token", help="use this existing device token; skips the pairing flow")
    p.add_argument("--property-id", help="property ID (auto-detected after pairing; required with --token)")
    p.add_argument(
        "--reset",
        action="store_true",
        help="revoke an already-active simulated device, then re-pair it (makes reruns easy)",
    )
    p.add_argument(
        "--initial-mode",
        choices=[UNARMED, ARMED, ARMED_AWAY],
        help=f"set this mode after pairing (choices: {UNARMED!r}, armed, armed_away)",
    )
    p.add_argument("--scenario", default="all", choices=SCENARIOS, help="scenario to run (default: all)")
    p.add_argument("--duration", type=float, default=60.0, help="seconds per scenario (ignored for 'all'; stages are fixed)")
    p.add_argument("--interval", type=float, default=5.0, help="telemetry publish interval in seconds (default: 5)")
    p.add_argument("--start-sequence", type=int, default=0, help="first telemetry sequence to publish (default: 0)")
    p.add_argument("--quiet", action="store_true", help="suppress the timeline log")
    args = p.parse_args(argv)
    if args.interval <= 0:
        p.error("--interval must be > 0")
    if args.duration < 0:
        p.error("--duration must be >= 0")

    with httpx.Client(base_url=args.base_url, timeout=10) as client:
        user_token = _login(client, args.user_email, args.user_password)
        if user_token is None:
            user_token = _register(client, args.user_name, args.user_email, args.user_password)
        if user_token is None:
            p.error(f"could not login or register user {args.user_email!r}")

        headers = {"Authorization": f"Bearer {user_token}"}
        if args.token:
            device_token = args.token
            property_id = args.property_id
            if not property_id:
                r = client.get("/api/v1/devices", headers=headers)
                r.raise_for_status()
                for d in r.json():
                    if d.get("device_id") == args.device_id:
                        property_id = d.get("property_id")
                        break
            if not property_id:
                p.error("could not determine property_id; pass --property-id")
            print(f"[sim] using existing device {args.device_id} (property {property_id})")
        else:
            # Real pairing flow (SPEC §3): pair-start -> claim.
            r = client.post(f"/api/v1/devices/{args.device_id}/pair-start")
            if r.status_code == 409:
                if not args.reset:
                    p.error(
                        f"device {args.device_id!r} is already active; rerun with --reset "
                        "to revoke and re-pair it, or pass a different --device-id"
                    )
                r = client.delete(f"/api/v1/devices/{args.device_id}", headers=headers)
                if r.status_code not in (200, 404):
                    p.error(f"could not reset device: {_error_text(r)}")
                r = client.post(f"/api/v1/devices/{args.device_id}/pair-start")
            if r.status_code != 200:
                p.error(f"pair-start failed: {_error_text(r)}")
            r = client.post("/api/v1/pair", json={"token": r.json()["token"]}, headers=headers)
            if r.status_code != 200:
                p.error(f"pairing failed: {_error_text(r)}")
            data = r.json()
            device_token = data["device_token"]
            property_id = args.property_id or data["property_id"]
            print(f"[sim] paired device {data['device_id']} on property {property_id}")

        sim = Simulator(
            client,
            device_id=args.device_id,
            device_token=device_token,
            property_id=property_id,
            user_token=user_token,
            interval=args.interval,
            verbose=not args.quiet,
            sequence=args.start_sequence,
        )
        sim.discover_sequence()
        if args.initial_mode:
            sim.set_mode(args.initial_mode)
        sim.run(args.scenario, args.duration, interval=args.interval)

        r = client.get("/api/v1/alerts", headers=headers)
        r.raise_for_status()
        open_alerts = [(a["signal"], a["severity"]) for a in r.json()["items"] if a["status"] == "open"]
        print(f"[sim] done. open alerts: {open_alerts or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
