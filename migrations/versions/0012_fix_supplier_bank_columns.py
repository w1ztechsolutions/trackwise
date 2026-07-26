"""fix_supplier_bank_columns

Revision ID: 0012_fix_supplier_bank_columns
Revises: dadc766a1512
Create Date: 2026-07-26 20:18:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0012_fix_supplier_bank_columns'
down_revision = '432fc643a066'
branch_labels = None
depends_on = None


def upgrade():
    # Add bank detail columns to suppliers table
    with op.batch_alter_table('suppliers') as batch_op:
        batch_op.add_column(sa.Column('bank_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('bank_branch', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('bank_account_number', sa.String(length=50), nullable=True))

    # Migrate any existing data from bank_details to the new columns
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT id, bank_details FROM suppliers WHERE bank_details IS NOT NULL"))
    for row in result:
        # Split bank_details if it contains a pattern, otherwise just put it in bank_name
        bank_details = row[1]
        # Simple approach: put the full bank_details in bank_name
        conn.execute(
            sa.text("UPDATE suppliers SET bank_name = :details WHERE id = :id"),
            {"details": bank_details, "id": row[0]}
        )


def downgrade():
    # Remove bank detail columns from suppliers table
    with op.batch_alter_table('suppliers') as batch_op:
        batch_op.drop_column('bank_account_number')
        batch_op.drop_column('bank_branch')
        batch_op.drop_column('bank_name')
