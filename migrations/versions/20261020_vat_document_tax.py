"""Phase B VAT flows: document-level output tax on cash sales.

Adds sales.tax_amount (default 0.00) so a walk-in cash sale can carry
output VAT while total_revenue stays NET — the credit side of the 2200
VAT Payable posting. Purchases already carry input VAT via Bills, and the
invoice flow stores its own tax, so no other columns are needed.

Also merges the four outstanding migration heads into one lineage.

Revision ID: 20261020_vat_document_tax
Revises: 20261015_tax_engine, 0015, 20260817_add_bank_statements, 7f8a9b0c1d2e
Create Date: 2026-10-20
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20261020_vat_document_tax'
down_revision = ('20261015_tax_engine', '0015', '20260817_add_bank_statements', '7f8a9b0c1d2e')
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sales', sa.Column('tax_amount', sa.Numeric(14, 2), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('sales', 'tax_amount')
