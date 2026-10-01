"""Add branch and cost-center accounting dimensions.

Revision ID: 20260930_accounting_dimensions
Revises: 20260930_demo_workspaces
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa


revision = "20260930_accounting_dimensions"
down_revision = (
    "20260930_demo_workspaces",
    "20260930_audit_actor_snapshots",
    "20260930_expense_budgets",
)
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_branches_business",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "code", name="uq_business_branch_code"),
    )
    op.create_index("ix_branches_business_id", "branches", ["business_id"])

    op.create_table(
        "cost_centers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_cost_centers_business",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "code", name="uq_business_cost_center_code"),
    )
    op.create_index("ix_cost_centers_business_id", "cost_centers", ["business_id"])

    with op.batch_alter_table("journal_entries") as batch_op:
        batch_op.add_column(sa.Column("branch_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_journal_entries_branch",
            "branches",
            ["branch_id"],
            ["id"],
        )
        batch_op.create_index("ix_journal_entries_branch_id", ["branch_id"])

    with op.batch_alter_table("journal_lines") as batch_op:
        batch_op.add_column(sa.Column("cost_center_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_journal_lines_cost_center",
            "cost_centers",
            ["cost_center_id"],
            ["id"],
        )
        batch_op.create_index("ix_journal_lines_cost_center_id", ["cost_center_id"])


def downgrade():
    with op.batch_alter_table("journal_lines") as batch_op:
        batch_op.drop_index("ix_journal_lines_cost_center_id")
        batch_op.drop_constraint("fk_journal_lines_cost_center", type_="foreignkey")
        batch_op.drop_column("cost_center_id")

    with op.batch_alter_table("journal_entries") as batch_op:
        batch_op.drop_index("ix_journal_entries_branch_id")
        batch_op.drop_constraint("fk_journal_entries_branch", type_="foreignkey")
        batch_op.drop_column("branch_id")

    op.drop_index("ix_cost_centers_business_id", table_name="cost_centers")
    op.drop_table("cost_centers")
    op.drop_index("ix_branches_business_id", table_name="branches")
    op.drop_table("branches")
