"""Drop unused stripe_subscription_id from subscriptions.

Stripe subscription payments are not planned; the column was model-only
(no webhook handler or payment flow was ever implemented) and is being
removed to keep the schema honest.

Revision ID: 20261015_drop_stripe_subscription_id
Revises: 20261001_bank_recon_periods
Create Date: 2026-10-15
"""

# revision identifiers, used by Alembic.
revision = '20261015_drop_stripe_subscription_id'
down_revision = '20261001_bank_recon_periods'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_column('subscriptions', 'stripe_subscription_id')


def downgrade():
    op.add_column(
        'subscriptions',
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
    )
