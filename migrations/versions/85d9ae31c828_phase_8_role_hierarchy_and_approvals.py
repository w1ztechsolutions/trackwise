"""phase_8_role_hierarchy_and_approvals

Adds SuperAdmin, Approval models, must_change_password column, and
created_by_superadmin_id to businesses.

Revision ID: 85d9ae31c828
Revises: a907d24e2ef5
Create Date: 2026-07-21 18:46:59.893313
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '85d9ae31c828'
down_revision = 'a907d24e2ef5'
branch_labels = None
depends_on = None


def upgrade():
    # --- New tables: SuperAdmin, ApprovalConfig, ApprovalRequest, ApprovalAction ---

    op.create_table('super_admins',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_super_admins_email'), 'super_admins', ['email'], unique=True)

    op.create_table('approval_configs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('business_id', sa.Integer(), nullable=False),
    sa.Column('transaction_type', sa.String(length=50), nullable=False),
    sa.Column('levels', sa.Text(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('business_id', 'transaction_type', name='uq_business_approval_type')
    )
    op.create_index(op.f('ix_approval_configs_business_id'), 'approval_configs', ['business_id'], unique=False)

    op.create_table('approval_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('business_id', sa.Integer(), nullable=False),
    sa.Column('transaction_type', sa.String(length=50), nullable=False),
    sa.Column('transaction_id', sa.Integer(), nullable=False),
    sa.Column('current_level', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_approval_requests_business_id'), 'approval_requests', ['business_id'], unique=False)

    op.create_table('approval_actions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('approval_request_id', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=20), nullable=False),
    sa.Column('level', sa.Integer(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['approval_request_id'], ['approval_requests.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # --- New columns on existing tables ---
    with op.batch_alter_table('businesses') as batch_op:
        batch_op.add_column(sa.Column('created_by_superadmin_id', sa.Integer(), sa.ForeignKey('super_admins.id'), nullable=True))

    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    # Drop new columns
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('must_change_password')

    with op.batch_alter_table('businesses') as batch_op:
        batch_op.drop_column('created_by_superadmin_id')

    # Drop new tables
    op.drop_table('approval_actions')
    op.drop_table('approval_requests')
    op.drop_index(op.f('ix_approval_configs_business_id'), table_name='approval_configs')
    op.drop_table('approval_configs')
    op.drop_index(op.f('ix_super_admins_email'), table_name='super_admins')
    op.drop_table('super_admins')