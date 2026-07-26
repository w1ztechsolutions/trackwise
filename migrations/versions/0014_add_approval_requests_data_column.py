"""Add missing 'data' column to approval_requests table

The phase_8 migration (85d9ae31c828) created the approval_requests table
without a 'data' column, but the ApprovalRequest model and all route
code expects it. This migration adds the missing column.

Revision ID: 0014_add_approval_requests_data_column
Revises: 0013_fix_customer_bank_columns
Create Date: 2026-07-26 19:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0014'
down_revision = '0013_fix_customer_bank_columns'
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL does not need batch mode — use direct add_column
    op.add_column('approval_requests', sa.Column('data', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('approval_requests', 'data')

