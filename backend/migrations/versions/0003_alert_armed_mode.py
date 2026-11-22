"""Alert arming context: alerts.armed_mode.

Revision ID: 0003_alert_armed_mode
Revises: 0002_system_modes
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.models import Base

revision = "0003_alert_armed_mode"
down_revision = "0002_system_modes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("alerts")}
    if "armed_mode" not in cols:
        op.add_column("alerts", sa.Column("armed_mode", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("alerts", "armed_mode")
