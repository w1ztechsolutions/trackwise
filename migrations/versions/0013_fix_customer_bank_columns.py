"""fix_customer_bank_columns

Revision ID: 0013_fix_customer_bank_columns
Revises: 0012_fix_supplier_bank_columns
Create Date: 2026-07-26 20:35:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0013_fix_customer_bank_columns'
down_revision = '0012_fix_supplier_bank_columns'
branch_labels = None
depends_on = None


def upgrade():
    # Add bank detail columns to customers table
    with op.batch_alter_table('customers') as batch_op:
        batch_op.add_column(sa.Column('bank_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('bank_branch', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('bank_account_number', sa.String(length=50), nullable=True))


def downgrade():
    # Remove bank detail columns from customers table
    with op.batch_alter_table('customers') as batch_op:
        batch_op.drop_column('bank_account_number')
        batch_op.drop_column('bank_branch')
        batch_op.drop_column('bank_name')
