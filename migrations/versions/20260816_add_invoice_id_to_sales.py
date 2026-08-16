"""Add invoice_id column to sales table

Revision ID: 20260816_add_invoice_id_to_sales
Revises: 0014
Create Date: 2026-08-16 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260816_add_invoice_id_to_sales'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade():
    # Add invoice_id column to sales table
    op.add_column('sales', sa.Column('invoice_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_sales_invoice_id', 'sales', 'invoices', ['invoice_id'], ['id'])


def downgrade():
    # Drop foreign key and column
    op.drop_constraint('fk_sales_invoice_id', 'sales', type_='foreignkey')
    op.drop_column('sales', 'invoice_id')
