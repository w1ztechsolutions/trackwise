"""Add business_id column to all models for multi-tenant isolation

Tables affected:
  - products (+)
  - stock_transactions (+)
  - purchases (+)
  - purchase_items (+)
  - sales (+)
  - sale_items (+)
  - expenses (+)
  - settings (+ changes unique constraint)
  - material_usages (+)
  - finished_good_outputs (+)

Revision ID: b55c4e6f8a21
Revises: 75398fe5708b
Create Date: 2026-07-08 10:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'b55c4e6f8a21'
down_revision = '75398fe5708b'
branch_labels = None
depends_on = None


def upgrade():
    # products
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('business_id', sa.Integer(), nullable=True))

    # stock_transactions
    with op.batch_alter_table('stock_transactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('business_id', sa.Integer(), nullable=True))

    # purchases
    with op.batch_alter_table('purchases', schema=None) as batch_op:
        batch_op.add_column(sa.Column('business_id', sa.Integer(), nullable=True))

    # purchase_items
    with op.batch_alter_table('purchase_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('business_id', sa.Integer(), nullable=True))

    # sales
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.add_column(sa.Column('business_id', sa.Integer(), nullable=True))

    # sale_items
    with op.batch_alter_table('sale_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('business_id', sa.Integer(), nullable=True))

    # expenses
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('business_id', sa.Integer(), nullable=True))

    # settings - add business_id, drop old unique on key, add composite unique
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('business_id', sa.Integer(), nullable=True))
        batch_op.drop_constraint('uq_settings_key', type_='unique')
        batch_op.create_unique_constraint('uq_business_setting_key', ['business_id', 'key'])

    # material_usages
    with op.batch_alter_table('material_usages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('business_id', sa.Integer(), nullable=True))

    # finished_good_outputs
    with op.batch_alter_table('finished_good_outputs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('business_id', sa.Integer(), nullable=True))


def downgrade():
    # finished_good_outputs
    with op.batch_alter_table('finished_good_outputs', schema=None) as batch_op:
        batch_op.drop_column('business_id')

    # material_usages
    with op.batch_alter_table('material_usages', schema=None) as batch_op:
        batch_op.drop_column('business_id')

    # settings
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.drop_constraint('uq_business_setting_key', type_='unique')
        batch_op.create_unique_constraint('uq_settings_key', ['key'])
        batch_op.drop_column('business_id')

    # expenses
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_column('business_id')

    # sale_items
    with op.batch_alter_table('sale_items', schema=None) as batch_op:
        batch_op.drop_column('business_id')

    # sales
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.drop_column('business_id')

    # purchase_items
    with op.batch_alter_table('purchase_items', schema=None) as batch_op:
        batch_op.drop_column('business_id')

    # purchases
    with op.batch_alter_table('purchases', schema=None) as batch_op:
        batch_op.drop_column('business_id')

    # stock_transactions
    with op.batch_alter_table('stock_transactions', schema=None) as batch_op:
        batch_op.drop_column('business_id')

    # products
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('business_id')