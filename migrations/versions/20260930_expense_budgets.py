"""Add monthly expense budgets.

Revision ID: 20260930_expense_budgets
Revises: 20260930_demo_workspaces
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa


revision = "20260930_expense_budgets"
down_revision = "20260930_demo_workspaces"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "expense_budgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_expense_budget_business",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["chart_of_accounts.id"],
            name="fk_expense_budget_account",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_expense_budget_created_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id",
            "account_id",
            "period_start",
            name="uq_expense_budget_business_account_period",
        ),
    )
    op.create_index(
        "ix_expense_budgets_business_id",
        "expense_budgets",
        ["business_id"],
    )


def downgrade():
    op.drop_index("ix_expense_budgets_business_id", table_name="expense_budgets")
    op.drop_table("expense_budgets")
