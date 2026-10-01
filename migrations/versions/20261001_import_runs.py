"""Add import_runs table for spreadsheet import records and staging.

Revision ID: 20261001_import_runs
Revises: 20261001_payment_reversals
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_import_runs"
down_revision = "20261001_payment_reversals"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "import_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("actor_name", sa.String(length=120), nullable=True),
        sa.Column("actor_email", sa.String(length=120), nullable=True),
        sa.Column("entity", sa.String(length=50), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("column_map", sa.Text(), nullable=True),
        sa.Column("date_order", sa.String(length=3), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Text(), nullable=True),
        sa.Column("staged_rows", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"], name="fk_import_runs_business_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_import_runs_user_id", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["chart_of_accounts.id"], name="fk_import_runs_account_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_runs_business_id", "import_runs", ["business_id"])
    op.create_index(
        "ix_import_runs_business_status", "import_runs", ["business_id", "status"]
    )


def downgrade():
    op.drop_index("ix_import_runs_business_status", table_name="import_runs")
    op.drop_index("ix_import_runs_business_id", table_name="import_runs")
    op.drop_table("import_runs")