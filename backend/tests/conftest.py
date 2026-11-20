from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main, pairing
from app.database import Base, get_db
from app.models import (
    AlertSubscription,
    Device,
    DeviceToken,
    Property,
    PropertyMember,
    User,
)
from app.security import hash_password, hash_token, new_device_token


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def override_get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    main.app.dependency_overrides[get_db] = override_get_db
    session = factory()
    yield session
    session.close()
    pairing._RATE_LIMITS.clear()


@pytest.fixture()
def client(db):
    return TestClient(main.app)


def create_user(
    db,
    *,
    email="alice@example.com",
    name="Alice",
    role="owner",
    password="pw123456",
    property_name="Home",
):
    user = User(name=name, email=email, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    prop = Property(name=property_name)
    db.add(prop)
    db.flush()
    db.add(PropertyMember(user_id=user.id, property_id=prop.id, role=role))
    db.add(AlertSubscription(property_id=prop.id, user_id=user.id, channels=["push"]))
    db.commit()
    return user, prop


def login(client, email, password="pw123456"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def make_device(db, property_id, device_id="esp32-1", status="active"):
    device = Device(device_id=device_id, property_id=property_id, status=status)
    db.add(device)
    db.commit()
    return device


def make_device_token(db, device_id, token=None):
    token = token or new_device_token()
    db.add(DeviceToken(device_id=device_id, token_hash=hash_token(token)))
    db.commit()
    return token


def pair_start(client, device_id):
    r = client.post(f"/api/v1/devices/{device_id}/pair-start")
    assert r.status_code == 200, r.text
    return r.json()


def ingest(client, device_id, token, seq, **fields):
    body = {"device_id": device_id, "sequence": seq, **fields}
    return client.post("/api/v1/ingest/telemetry", json=body, headers={"Authorization": f"Bearer {token}"})
