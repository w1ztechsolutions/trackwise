"""Budget planning tables with backfill from legacy expense budgets.

Revision ID: 20261001_budget_planning
Revises: 20260930_accounting_dimensions
Create Date: 2026-10-01
"""

from datetime import date, timedelta

from alembic import op
import sqlalchemy as sa


revision = "20261001_budget_planning"
down_revision = "20260930_accounting_dimensions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("budget_type", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "budget_type IN ('revenue', 'expense')", name="ck_budget_type"
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'archived')", name="ck_budget_status"
        ),
        sa.CheckConstraint("period_end >= period_start", name="ck_budget_period"),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_budget_business",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_budget_created_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_budgets_business_id", "budgets", ["business_id"])

    op.create_table(
        "budget_line_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("budget_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("cost_center_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("amount >= 0", name="ck_budget_line_amount"),
        sa.ForeignKeyConstraint(
            ["budget_id"],
            ["budgets.id"],
            name="fk_budget_line_budget",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["chart_of_accounts.id"],
            name="fk_budget_line_account",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cost_center_id"],
            ["cost_centers.id"],
            name="fk_budget_line_cost_center",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "budget_id",
            "account_id",
            "cost_center_id",
            name="uq_budget_line_account_cost_center",
        ),
    )
    op.create_index(
        "ix_budget_line_items_budget_id", "budget_line_items", ["budget_id"]
    )
    op.create_index(
        "ix_budget_line_items_cost_center_id",
        "budget_line_items",
        ["cost_center_id"],
    )

    _backfill_legacy_budgets()


def _backfill_legacy_budgets():
    """Copy each legacy expense budget into a single-line Budget record.

    The legacy ``expense_budgets`` table is kept for backward compatibility;
    these rows make the existing figures visible in the new budget reports.
    """
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, business_id, account_id, period_start, amount, created_by, "
            "created_at FROM expense_budgets ORDER BY business_id, period_start, id"
        )
    ).fetchall()
    if not rows:
        return

    for row in rows:
        period_start = row.period_start
        next_month = (
            date(period_start.year + 1, 1, 1)
            if period_start.month == 12
            else date(period_start.year, period_start.month + 1, 1)
        )
        budget_id = connection.execute(
            sa.text(
                "INSERT INTO budgets (business_id, name, budget_type, period_start, "
                "period_end, status, created_by, created_at) "
                "VALUES (:business_id, :name, 'expense', :period_start, :period_end, "
                "'draft', :created_by, :created_at) RETURNING id"
            ),
            {
                'business_id': row.business_id,
                'name': f"Auto: account {row.account_id} {period_start.isoformat()}",
                'period_start': period_start,
                'period_end': next_month - timedelta(days=1),
                'created_by': row.created_by,
                'created_at': row.created_at,
            },
        ).scalar()
        connection.execute(
            sa.text(
                "INSERT INTO budget_line_items (budget_id, account_id, cost_center_id, "
                "amount, notes) VALUES (:budget_id, :account_id, NULL, :amount, NULL)"
            ),
            {
                'budget_id': budget_id,
                'account_id': row.account_id,
                'amount': row.amount,
            },
        )


def downgrade():
    op.drop_index("ix_budget_line_items_cost_center_id", table_name="budget_line_items")
    op.drop_index("ix_budget_line_items_budget_id", table_name="budget_line_items")
    op.drop_table("budget_line_items")
    op.drop_index("ix_budgets_business_id", table_name="budgets")
    op.drop_table("budgets")