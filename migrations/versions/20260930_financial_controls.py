"""Add journal reversals, period close, and revenue recognition schedules.

Revision ID: 20260930_financial_controls
Revises: 20260817_merge_heads
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa


revision = "20260930_financial_controls"
down_revision = "20260817_merge_heads"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "businesses",
        sa.Column("last_closed_period_date", sa.Date(), nullable=True),
    )
    with op.batch_alter_table("journal_entries") as batch_op:
        batch_op.add_column(
            sa.Column("reversed_by_entry_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("reversal_reason", sa.String(length=255), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_journal_entries_reversed_by_entry",
            "journal_entries",
            ["reversed_by_entry_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_journal_entries_reversed_by_entry_id",
            ["reversed_by_entry_id"],
        )

    op.create_table(
        "revenue_recognition_schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("revenue_account_id", sa.Integer(), nullable=False),
        sa.Column("deferred_revenue_account_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "recognized_amount",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_recognized_through", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_revenue_schedule_business",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name="fk_revenue_schedule_invoice",
        ),
        sa.ForeignKeyConstraint(
            ["revenue_account_id"],
            ["chart_of_accounts.id"],
            name="fk_revenue_schedule_revenue_account",
        ),
        sa.ForeignKeyConstraint(
            ["deferred_revenue_account_id"],
            ["chart_of_accounts.id"],
            name="fk_revenue_schedule_deferred_account",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_revenue_schedule_created_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_id", name="uq_revenue_schedule_invoice"),
    )
    op.create_index(
        "ix_revenue_recognition_schedules_business_id",
        "revenue_recognition_schedules",
        ["business_id"],
    )


def downgrade():
    op.drop_index(
        "ix_revenue_recognition_schedules_business_id",
        table_name="revenue_recognition_schedules",
    )
    op.drop_table("revenue_recognition_schedules")
    with op.batch_alter_table("journal_entries") as batch_op:
        batch_op.drop_constraint(
            "uq_journal_entries_reversed_by_entry_id",
            type_="unique",
        )
        batch_op.drop_constraint(
            "fk_journal_entries_reversed_by_entry",
            type_="foreignkey",
        )
        batch_op.drop_column("reversal_reason")
        batch_op.drop_column("reversed_by_entry_id")
    op.drop_column("businesses", "last_closed_period_date")
