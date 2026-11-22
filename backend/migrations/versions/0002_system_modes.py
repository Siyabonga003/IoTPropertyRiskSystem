"""System modes: unarmed/armed/armed_away + telemetry armed_mode.

Revision ID: 0002_system_modes
Revises: 0001_initial
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.models import Base

revision = "0002_system_modes"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # system_modes + system_mode_history tables (no-op if already created)
    Base.metadata.create_all(bind=op.get_bind())
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("telemetry_events")}
    if "armed_mode" not in cols:
        op.add_column("telemetry_events", sa.Column("armed_mode", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("telemetry_events", "armed_mode")
    op.drop_table("system_mode_history")
    op.drop_table("system_modes")
