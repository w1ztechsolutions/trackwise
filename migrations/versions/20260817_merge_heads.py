"""Merge multiple migration heads

Revision ID: 20260817_merge_heads
Revises: 7f8a9b0c1d2e, 0015, 20260817_add_bank_statements
Create Date: 2026-08-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260817_merge_heads"
down_revision = ("7f8a9b0c1d2e", "0015", "20260817_add_bank_statements")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass

