"""increase transaction_type length for production services

Revision ID: 75398fe5708b
Revises: 1d03f23621da
Create Date: 2026-07-08 05:56:44.898079
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '75398fe5708b'
down_revision = '1d03f23621da'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('stock_transactions', schema=None) as batch_op:
        batch_op.alter_column('transaction_type',
                              existing_type=sa.String(length=20),
                              type_=sa.String(length=30),
                              existing_nullable=False,
                              existing_server_default='PURCHASE')


def downgrade():
    with op.batch_alter_table('stock_transactions', schema=None) as batch_op:
        batch_op.alter_column('transaction_type',
                              existing_type=sa.String(length=30),
                              type_=sa.String(length=20),
                              existing_nullable=False,
                              existing_server_default='PURCHASE')
