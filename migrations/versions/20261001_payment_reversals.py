"""Add payment reversal tracking.

Revision ID: 20261001_payment_reversals
Revises: 20261001_expenditure_returns
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_payment_reversals"
down_revision = "20261001_expenditure_returns"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "payments",
        sa.Column("is_reversed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "payments",
        sa.Column("reversal_reason", sa.String(length=255), nullable=True),
    )
    op.add_column("payments", sa.Column("reversal_date", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("payments", "reversal_date")
    op.drop_column("payments", "reversal_reason")
    op.drop_column("payments", "is_reversed")