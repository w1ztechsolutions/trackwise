"""Add BankReconciliationPeriod table for bank reconciliation period locks.

Revision ID: 20261001_bank_recon_periods
Revises: 20261001_import_runs
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa


revision = "20261001_bank_recon_periods"
down_revision = "20261001_import_runs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bank_reconciliation_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False, index=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("closed_by", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("reopened_by", sa.Integer(), nullable=True),
        sa.Column("reopened_at", sa.DateTime(), nullable=True),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_bank_recon_periods_business_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["chart_of_accounts.id"],
            name="fk_bank_recon_periods_account_id",
        ),
        sa.ForeignKeyConstraint(
            ["closed_by"],
            ["users.id"],
            name="fk_bank_recon_periods_closed_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reopened_by"],
            ["users.id"],
            name="fk_bank_recon_periods_reopened_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id", "account_id", "period_end",
            name="uq_bank_recon_periods_business_account_period"
        ),
    )
    op.create_index(
        "ix_bank_recon_periods_business_id",
        "bank_reconciliation_periods",
        ["business_id"],
    )
    op.create_index(
        "ix_bank_recon_periods_account_id",
        "bank_reconciliation_periods",
        ["account_id"],
    )
    op.create_index(
        "ix_bank_recon_periods_is_locked",
        "bank_reconciliation_periods",
        ["is_locked"],
    )


def downgrade():
    op.drop_index(
        "ix_bank_recon_periods_is_locked",
        table_name="bank_reconciliation_periods",
    )
    op.drop_index(
        "ix_bank_recon_periods_account_id",
        table_name="bank_reconciliation_periods",
    )
    op.drop_index(
        "ix_bank_recon_periods_business_id",
        table_name="bank_reconciliation_periods",
    )
    op.drop_table("bank_reconciliation_periods")