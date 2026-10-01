"""Expenditure returns (bill credit notes and cash refunds)."""

from alembic import op
import sqlalchemy as sa


revision = "20261001_expenditure_returns"
down_revision = "20261001_budget_planning"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "purchase_returns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("bill_id", sa.Integer(), nullable=True),
        sa.Column("supplier_id", sa.Integer(), nullable=True),
        sa.Column("return_date", sa.DateTime(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("return_type", sa.String(length=20), nullable=False),
        sa.Column("is_applied_to_ap", sa.Boolean(), nullable=False),
        sa.Column("journal_entry_id", sa.Integer(), nullable=True),
        sa.Column("is_reversed", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "return_type IN ('credit_note', 'refund')",
            name="ck_purchase_return_type",
        ),
        sa.CheckConstraint("amount > 0", name="ck_purchase_return_amount"),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_purchase_return_business",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["bill_id"],
            ["bills.id"],
            name="fk_purchase_return_bill",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_purchase_return_supplier",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"],
            ["journal_entries.id"],
            name="fk_purchase_return_journal_entry",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_purchase_return_created_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_returns_business_id", "purchase_returns", ["business_id"])


def downgrade():
    op.drop_index("ix_purchase_returns_business_id", table_name="purchase_returns")
    op.drop_table("purchase_returns")