from __future__ import annotations

import os
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Config:
    # Database (SQLite for dev/tests; PostgreSQL recommended for prod).
    DATABASE_URL: str = _env("IOTPRM_DATABASE_URL", "sqlite:///data/iot.db")
    # JWT secret for user access tokens.
    SECRET_KEY: str = _env("IOTPRM_SECRET_KEY", "dev-secret-change-me-iot-property-risk-42-chars!!")
    # Base URL used when building QR links in pair-start responses.
    PUBLIC_URL: str = _env("IOTPRM_PUBLIC_URL", "http://localhost:8000")
    # Disconnect sweeper cadence and staleness window.
    SWEEP_INTERVAL_SECONDS: float = float(_env("IOTPRM_SWEEP_INTERVAL_SECONDS", "30"))
    TELEMETRY_TIMEOUT_MINUTES: float = float(_env("IOTPRM_TELEMETRY_TIMEOUT_MINUTES", "5"))
    # Pairing token TTL (single use, stored hashed).
    PAIRING_TOKEN_TTL_SECONDS: int = _int_env("IOTPRM_PAIRING_TOKEN_TTL_SECONDS", 600)
    # Notification providers (optional; when unset, notifications are recorded only).
    SMTP_HOST: str = _env("IOTPRM_SMTP_HOST", "")
    SMTP_PORT: int = _int_env("IOTPRM_SMTP_PORT", 587)
    SMTP_USER: str = _env("IOTPRM_SMTP_USER", "")
    SMTP_PASSWORD: str = _env("IOTPRM_SMTP_PASSWORD", "")
    SMTP_FROM: str = _env("IOTPRM_SMTP_FROM", "iotprm@example.com")
    TWILIO_ACCOUNT_SID: str = _env("IOTPRM_TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = _env("IOTPRM_TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM: str = _env("IOTPRM_TWILIO_FROM", "")


config = Config()

# Ensure the SQLite directory exists when the database URL points to a file path.
if config.DATABASE_URL.startswith("sqlite:"):
    db_path = config.DATABASE_URL.removeprefix("sqlite:///")
    parent = Path(db_path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)
