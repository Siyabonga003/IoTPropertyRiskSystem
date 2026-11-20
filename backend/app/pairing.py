from __future__ import annotations

import secrets
import time
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from app.config import config
from app.models import Device, DeviceToken, PairingToken
from app.risk import as_utc
from app.security import hash_token, new_device_token, user_property_ids

_RATE_LIMITS: dict[str, list[float]] = {}


def _is_rate_limited(key: str, limit: int = 5, window_seconds: float = 60.0) -> bool:
    now = time.monotonic()
    bucket = _RATE_LIMITS.setdefault(key, [])
    _RATE_LIMITS[key] = [t for t in bucket if now - t < window_seconds]
    if len(_RATE_LIMITS[key]) >= limit:
        return True
    _RATE_LIMITS[key].append(now)
    return False


def pair_start(db, device_id: str) -> dict:
    """Create a pairing token + QR URL for a device entering pairing mode."""
    if _is_rate_limited(f"pair_start:{device_id}"):
        raise HTTPException(status_code=429, detail="RATE_LIMITED")
    device = db.query(Device).filter_by(device_id=device_id).one_or_none()
    if device is None:
        device = Device(device_id=device_id)
        db.add(device)
    elif device.status == "active":
        raise HTTPException(status_code=409, detail="DEVICE_ACTIVE")
    device.status = "pairing"
    token = "pt_" + secrets.token_hex(12)
    now = datetime.now(UTC)
    pairing = PairingToken(
        device_id=device_id,
        token_hash=hash_token(token),
        qr_url=f"{config.PUBLIC_URL}/pair?token={token}",
        expires_at=now + timedelta(seconds=config.PAIRING_TOKEN_TTL_SECONDS),
        consumed_at=None,
        device_token=None,
        created_at=now,
    )
    db.add(pairing)
    db.commit()
    return {
        "device_id": device_id,
        "token": token,
        "qr_url": pairing.qr_url,
        "expires_at": pairing.expires_at.isoformat(),
    }


def _get_pairing_token(db, device_id: str, token: str) -> PairingToken:
    pairing = db.query(PairingToken).filter_by(device_id=device_id, token_hash=hash_token(token)).one_or_none()
    if pairing is None or as_utc(pairing.expires_at) <= datetime.now(UTC):
        raise HTTPException(status_code=401, detail="TOKEN_INVALID")
    return pairing


def pair_status(db, device_id: str, token: str) -> dict:
    """Device polls status while pairing; returns device_token once claimed."""
    pairing = _get_pairing_token(db, device_id, token)
    if pairing.consumed_at is not None:
        return {"status": "active", "device_token": pairing.device_token}
    return {"status": "pairing"}


def pair_claim(db, user_id: str, token: str, property_id: str | None = None) -> dict:
    """Mobile app claims a pairing token; issues the device credential."""
    pairing = db.query(PairingToken).filter_by(token_hash=hash_token(token)).one_or_none()
    if pairing is None or as_utc(pairing.expires_at) <= datetime.now(UTC) or pairing.consumed_at is not None:
        raise HTTPException(status_code=401, detail="TOKEN_INVALID")
    device = db.query(Device).filter_by(device_id=pairing.device_id).one_or_none()
    if device is None or device.status != "pairing":
        raise HTTPException(status_code=409, detail="PAIRING_UNAVAILABLE")
    memberships = user_property_ids(db, user_id)
    if property_id is not None:
        if property_id not in memberships:
            raise HTTPException(status_code=403, detail="FORBIDDEN")
    else:
        if not memberships:
            raise HTTPException(status_code=403, detail="USER_HAS_NO_PROPERTY")
        property_id = memberships[0]
    device_token = new_device_token()
    db.add(DeviceToken(device_id=device.device_id, token_hash=hash_token(device_token)))
    device.status = "active"
    device.property_id = property_id
    device.paired_at = datetime.now(UTC)
    pairing.consumed_at = device.paired_at
    pairing.device_token = device_token
    db.commit()
    return {"device_id": device.device_id, "property_id": property_id, "device_token": device_token}
