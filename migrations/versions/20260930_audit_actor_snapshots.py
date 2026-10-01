"""Snapshot audit actor identity on each audit record.

Revision ID: 20260930_audit_actor_snapshots
Revises: 20260930_financial_controls
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa


revision = "20260930_audit_actor_snapshots"
down_revision = "20260930_financial_controls"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("audit_logs", sa.Column("actor_name", sa.String(length=120), nullable=True))
    op.add_column("audit_logs", sa.Column("actor_email", sa.String(length=120), nullable=True))


def downgrade():
    op.drop_column("audit_logs", "actor_email")
    op.drop_column("audit_logs", "actor_name")
