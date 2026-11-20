from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request

from app.config import config
from app.database import get_db
from app.models import Device, DeviceToken, PropertyMember, User


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_device_token() -> str:
    return "dt_" + secrets.token_hex(16)


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return f"pbkdf2-sha256${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        _, salt, digest = stored_hash.split("$")
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return hmac.compare_digest(candidate, digest)


def new_user_token(user_id: str) -> str:
    payload: dict[str, Any] = {"sub": user_id, "type": "user", "iat": int(time.time())}
    return jwt.encode(payload, config.SECRET_KEY, algorithm="HS256")


def decode_user_token(token: str) -> dict[str, Any] | None:
    try:
        claims = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if claims.get("type") != "user" or not isinstance(claims.get("sub"), str):
        return None
    return claims


def bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")
    return token


def user_property_ids(db, user_id: str) -> list[str]:
    return [m.property_id for m in db.query(PropertyMember).filter_by(user_id=user_id).all()]


def require_role(db, user_id: str, property_id: str, allowed: set[str]) -> None:
    member = db.query(PropertyMember).filter_by(user_id=user_id, property_id=property_id).one_or_none()
    if member is None or member.role not in allowed:
        raise HTTPException(status_code=403, detail="FORBIDDEN")


async def get_current_user(request: Request, db=Depends(get_db)) -> User:
    token = bearer_token(request)
    claims = decode_user_token(token)
    if claims is None:
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")
    user = db.get(User, claims["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")
    return user


async def get_current_device(request: Request, db=Depends(get_db)) -> Device:
    token = bearer_token(request)
    token_rec = db.query(DeviceToken).filter_by(token_hash=hash_token(token)).one_or_none()
    if token_rec is None or token_rec.revoked_at is not None:
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")
    device = db.query(Device).filter_by(device_id=token_rec.device_id).one_or_none()
    if device is None or device.status == "revoked":
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")
    return device
