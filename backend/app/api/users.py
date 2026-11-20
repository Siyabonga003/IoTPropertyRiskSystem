from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.serializers import serialize_property, serialize_user
from app.database import get_db
from app.models import AlertSubscription, Property, PropertyMember, User
from app.security import (
    get_current_user,
    hash_password,
    new_user_token,
    user_property_ids,
    verify_password,
)

router = APIRouter()


@router.post("/api/v1/auth/login")
async def login(request: Request, db=Depends(get_db)):
    data = await request.json()
    email = data.get("email", "").strip()
    password = data.get("password", "")
    user = db.query(User).filter_by(email=email).one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")
    return {"access_token": new_user_token(user.id), "token_type": "bearer"}


@router.post("/api/v1/users")
async def register(request: Request, db=Depends(get_db)):
    data = await request.json()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")
    if not name or not email or len(password) < 6:
        raise HTTPException(status_code=422, detail="name, email and password (>=6 chars) required")
    if db.query(User).filter_by(email=email).one_or_none():
        raise HTTPException(status_code=409, detail="EMAIL_TAKEN")
    user = User(name=name, email=email, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    prop = Property(name="Home")
    db.add(prop)
    db.flush()
    db.add(PropertyMember(user_id=user.id, property_id=prop.id, role="owner"))
    db.add(AlertSubscription(property_id=prop.id, user_id=user.id, channels=["push"]))
    db.commit()
    return {
        "access_token": new_user_token(user.id),
        "user": serialize_user(user),
        "property": serialize_property(prop),
    }


@router.get("/api/v1/me")
def me(user=Depends(get_current_user), db=Depends(get_db)):
    memberships = (
        db.query(PropertyMember)
        .join(Property, Property.id == PropertyMember.property_id)
        .filter(PropertyMember.user_id == user.id)
        .order_by(PropertyMember.joined_at)
        .all()
    )
    return {**serialize_user(user), "properties": [serialize_property(db.get(Property, m.property_id)) for m in memberships]}


@router.get("/api/v1/properties/{property_id}")
def get_property(property_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    if property_id not in user_property_ids(db, user.id):
        raise HTTPException(status_code=404, detail="Not found")
    prop = db.get(Property, property_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="Not found")
    return serialize_property(prop)


@router.get("/api/v1/alert_subscriptions")
def list_subscriptions(user=Depends(get_current_user), db=Depends(get_db)):
    subs = db.query(AlertSubscription).filter_by(user_id=user.id).all()
    return [
        {"id": s.id, "property_id": s.property_id, "channels": s.channels or ["push"]}
        for s in subs
    ]


@router.put("/api/v1/alert_subscriptions/{property_id}")
async def put_subscription(
    property_id: str,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    if property_id not in user_property_ids(db, user.id):
        raise HTTPException(status_code=404, detail="Not found")
    data = await request.json()
    channels = data.get("channels", ["push"])
    if not isinstance(channels, list):
        raise HTTPException(status_code=422, detail="channels must be a list")
    sub = (
        db.query(AlertSubscription)
        .filter_by(property_id=property_id, user_id=user.id)
        .one_or_none()
    )
    if sub is None:
        sub = AlertSubscription(property_id=property_id, user_id=user.id)
        db.add(sub)
    sub.channels = [c for c in channels if c in ("push", "email", "sms")]
    db.commit()
    return {"id": sub.id, "property_id": sub.property_id, "channels": sub.channels}
