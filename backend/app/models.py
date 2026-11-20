from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, declarative_base, mapped_column

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(UTC)


def _id(prefix: str) -> str:
    return prefix + secrets.token_hex(8)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _id("usr_"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _id("prp_"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    risk_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PropertyMember(Base):
    __tablename__ = "property_members"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _id("mem_"))
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    property_id: Mapped[str] = mapped_column(String(32), ForeignKey("properties.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("user_id", "property_id", name="uq_property_members"),)


class Device(Base):
    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    property_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("properties.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    firmware_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pairing", index=True)
    paired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    risk_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sensor_levels: Mapped[dict | None] = mapped_column(JSON, nullable=False, default=dict)
    last_smoke_ppm: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_gas_ppm: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_flame_detected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_water_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_motion_detected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_occupancy: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    battery_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rssi_dbm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_health: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")
    faults: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _id("dtk_"))
    device_id: Mapped[str] = mapped_column(String(64), ForeignKey("devices.device_id"), nullable=False, unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PairingToken(Base):
    __tablename__ = "pairing_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _id("prt_"))
    device_id: Mapped[str] = mapped_column(String(64), ForeignKey("devices.device_id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    qr_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    device_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _id("tel_"))
    device_id: Mapped[str] = mapped_column(String(64), ForeignKey("devices.device_id"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    property_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("properties.id"), nullable=True, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    smoke_ppm: Mapped[float | None] = mapped_column(Float, nullable=True)
    gas_ppm: Mapped[float | None] = mapped_column(Float, nullable=True)
    flame_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    water_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    motion_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    occupancy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    battery_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rssi_dbm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_health: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")
    device_risk: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    faults: Mapped[list | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (UniqueConstraint("device_id", "sequence", name="uq_telemetry_dedup"),)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _id("alr_"))
    property_id: Mapped[str] = mapped_column(String(32), ForeignKey("properties.id"), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(64), ForeignKey("devices.device_id"), nullable=False, index=True)
    signal: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    notes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AlertNotification(Base):
    __tablename__ = "alert_notifications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _id("ntf_"))
    alert_id: Mapped[str] = mapped_column(String(32), ForeignKey("alerts.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="sent")
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AlertSubscription(Base):
    __tablename__ = "alert_subscriptions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _id("sub_"))
    property_id: Mapped[str] = mapped_column(String(32), ForeignKey("properties.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    channels: Mapped[list] = mapped_column(JSON, nullable=False, default=lambda: ["push"])

    __table_args__ = (UniqueConstraint("property_id", "user_id", name="uq_alert_subscriptions"),)
