"""add missing payment columns and accounting tables

Revision ID: 7f8a9b0c1d2e
Revises: dadc766a1512
Create Date: 2026-08-16 18:10:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7f8a9b0c1d2e'
down_revision = 'dadc766a1512'
branch_labels = None
depends_on = None


def upgrade():
    # Create missing accounting tables
    op.create_table(
        'financial_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('business_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_financial_categories_business_id'), 'financial_categories', ['business_id'], unique=False)

    op.create_table(
        'line_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('business_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=True),
        sa.Column('account_code', sa.String(length=20), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['financial_categories.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_line_items_business_id'), 'line_items', ['business_id'], unique=False)

    op.create_table(
        'staff',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('business_id', sa.Integer(), nullable=False),
        sa.Column('staff_id', sa.String(length=20), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('role', sa.String(length=100), nullable=True),
        sa.Column('department', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_staff_business_id'), 'staff', ['business_id'], unique=False)
    op.create_unique_constraint(None, 'staff', ['staff_id'])

    # Add missing columns to payments
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('line_item_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('staff_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('payee_type', sa.String(length=20), nullable=False, server_default='supplier'))
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'))
        batch_op.alter_column('payment_method', new_column_name='payment_mode')

    # Add foreign key constraints for payments
    op.create_foreign_key(None, 'payments', 'financial_categories', ['category_id'], ['id'])
    op.create_foreign_key(None, 'payments', 'line_items', ['line_item_id'], ['id'])
    op.create_foreign_key(None, 'payments', 'staff', ['staff_id'], ['id'])


def downgrade():
    # Remove foreign key constraints
    op.drop_constraint(None, 'payments', type_='foreignkey')
    op.drop_constraint(None, 'payments', type_='foreignkey')
    op.drop_constraint(None, 'payments', type_='foreignkey')

    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.alter_column('payment_mode', new_column_name='payment_method')
        batch_op.drop_column('status')
        batch_op.drop_column('description')
        batch_op.drop_column('payee_type')
        batch_op.drop_column('staff_id')
        batch_op.drop_column('line_item_id')
        batch_op.drop_column('category_id')

    op.drop_constraint(None, 'staff', type_='unique')
    op.drop_index(op.f('ix_staff_business_id'), table_name='staff')
    op.drop_table('staff')

    op.drop_index(op.f('ix_line_items_business_id'), table_name='line_items')
    op.drop_table('line_items')

    op.drop_index(op.f('ix_financial_categories_business_id'), table_name='financial_categories')
    op.drop_table('financial_categories')
