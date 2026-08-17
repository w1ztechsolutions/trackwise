"""Add BankStatement model for bank reconciliation

Revision ID: 20260817_add_bank_statements
Revises: 20260816_add_invoice_id_to_sales
Create Date: 2026-08-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260817_add_bank_statements'
down_revision = '20260816_add_invoice_id_to_sales'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'bank_statements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('business_id', sa.Integer(), nullable=False, index=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('statement_date', sa.DateTime(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('reference', sa.String(length=100), nullable=True),
        sa.Column('is_reconciled', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('journal_entry_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['chart_of_accounts.id'], ),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['journal_entry_id'], ['journal_entries.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bank_statements_business_id'), 'bank_statements', ['business_id'], unique=False)
    op.create_index(op.f('ix_bank_statements_account_id'), 'bank_statements', ['account_id'], unique=False)
    op.create_index(op.f('ix_bank_statements_is_reconciled'), 'bank_statements', ['is_reconciled'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_bank_statements_is_reconciled'), table_name='bank_statements')
    op.drop_index(op.f('ix_bank_statements_account_id'), table_name='bank_statements')
    op.drop_index(op.f('ix_bank_statements_business_id'), table_name='bank_statements')
    op.drop_table('bank_statements')
