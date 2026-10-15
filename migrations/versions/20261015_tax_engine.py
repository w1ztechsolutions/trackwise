"""Malawi tax engine: tax_codes and tax_rates tables, line tax code links.

Adds effective-dated tax codes (VAT standard / zero-rated / exempt, and
future WHT types) with per-business scoping, and links invoice/bill line
items to a tax code so rates are resolved by effective date rather than
free-typed per line.

Revision ID: 20261015_tax_engine
Revises: 20261015_drop_stripe_subscription_id
Create Date: 2026-10-15
"""

# revision identifiers, used by Alembic.
revision = '20261015_tax_engine'
down_revision = '20261015_drop_stripe_subscription_id'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'tax_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('business_id', sa.Integer(), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('tax_type', sa.String(length=20), nullable=False, server_default='vat'),
        sa.Column('treatment', sa.String(length=20), nullable=False, server_default='standard'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint('business_id', 'code', name='uq_tax_code_business_code'),
    )
    op.create_table(
        'tax_rates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tax_code_id', sa.Integer(), sa.ForeignKey('tax_codes.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('rate', sa.Numeric(6, 4), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.UniqueConstraint('tax_code_id', 'effective_from', name='uq_tax_rate_code_effective'),
    )
    op.add_column('invoice_items', sa.Column('tax_code_id', sa.Integer(), sa.ForeignKey('tax_codes.id'), nullable=True))
    op.add_column('bill_items', sa.Column('tax_code_id', sa.Integer(), sa.ForeignKey('tax_codes.id'), nullable=True))


def downgrade():
    op.drop_column('bill_items', 'tax_code_id')
    op.drop_column('invoice_items', 'tax_code_id')
    op.drop_table('tax_rates')
    op.drop_table('tax_codes')
