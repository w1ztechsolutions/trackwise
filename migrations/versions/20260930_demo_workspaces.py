"""Add normalized name registry for isolated demo workspaces.

Revision ID: 20260930_demo_workspaces
Revises: 20260930_financial_controls
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa


revision = "20260930_demo_workspaces"
down_revision = "20260930_financial_controls"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "demo_workspaces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_demo_workspaces_business",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", name="uq_demo_workspaces_business_id"),
        sa.UniqueConstraint("normalized_name", name="uq_demo_workspaces_normalized_name"),
    )


def downgrade():
    op.drop_table("demo_workspaces")
