"""Subscription management service.

Handles plan selection, subscription lifecycle, and feature access control.
"""

import json
from datetime import datetime, timezone, timedelta
from models import db, Plan, Subscription


# Default plan definitions
DEFAULT_PLANS = [
    {
        'name': 'Free',
        'price': 0.0,
        'max_users': 1,
        'features': {
            'reports': True,
            'exports': False,
            'multi_user': False,
            'api_access': False,
            'priority_support': False,
        },
    },
    {
        'name': 'Starter',
        'price': 29.0,
        'max_users': 3,
        'features': {
            'reports': True,
            'exports': True,
            'multi_user': True,
            'api_access': False,
            'priority_support': False,
        },
    },
    {
        'name': 'Business',
        'price': 99.0,
        'max_users': 10,
        'features': {
            'reports': True,
            'exports': True,
            'multi_user': True,
            'api_access': True,
            'priority_support': False,
        },
    },
    {
        'name': 'Enterprise',
        'price': 299.0,
        'max_users': 999,
        'features': {
            'reports': True,
            'exports': True,
            'multi_user': True,
            'api_access': True,
            'priority_support': True,
        },
    },
]


def seed_default_plans():
    """Seed default subscription plans if none exist."""
    if Plan.query.first() is not None:
        return

    for plan_data in DEFAULT_PLANS:
        plan = Plan(
            name=plan_data['name'],
            price=plan_data['price'],
            max_users=plan_data['max_users'],
            features=json.dumps(plan_data['features']),
            is_active=True,
        )
        db.session.add(plan)
    db.session.commit()


def get_plan_by_name(name):
    """Get a plan by name."""
    return Plan.query.filter_by(name=name, is_active=True).first()


def get_plan_by_id(plan_id):
    """Get a plan by ID."""
    return db.session.get(Plan, plan_id)


def get_available_plans():
    """Get all active plans."""
    return Plan.query.filter_by(is_active=True).order_by(Plan.price.asc()).all()


def get_current_subscription(business_id):
    """Get the active subscription for a business."""
    if business_id is None:
        return None
    return Subscription.query.filter_by(
        business_id=business_id,
        status='active',
    ).first()


def subscribe(business_id, plan_id, payment_method=None):
    """Subscribe a business to a plan.

    Creates or updates the subscription. If an active subscription exists,
    it will be upgraded/downgraded.
    """
    if business_id is None:
        raise ValueError('business_id is required')

    plan = get_plan_by_id(plan_id)
    if not plan:
        raise ValueError(f'Plan {plan_id} not found')

    now = datetime.now(timezone.utc)
    renewal_date = now + timedelta(days=30)

    existing = Subscription.query.filter_by(business_id=business_id).first()
    if existing:
        existing.plan_id = plan.id
        existing.status = 'active'
        existing.renewal_date = renewal_date
        if payment_method:
            existing.payment_method = payment_method
        db.session.commit()
        return existing

    sub = Subscription(
        business_id=business_id,
        plan_id=plan.id,
        status='active',
        start_date=now,
        renewal_date=renewal_date,
        payment_method=payment_method,
    )
    db.session.add(sub)
    db.session.commit()
    return sub


def cancel_subscription(business_id):
    """Cancel an active subscription."""
    sub = get_current_subscription(business_id)
    if sub:
        sub.status = 'cancelled'
        db.session.commit()
    return sub


def check_access(business_id, feature_name):
    """Check if a business has access to a feature based on their plan."""
    if business_id is None:
        return True  # Backwards compatibility

    sub = get_current_subscription(business_id)
    if not sub:
        return False

    try:
        features = json.loads(sub.plan.features) if sub.plan.features else {}
        return features.get(feature_name, False)
    except (json.JSONDecodeError, AttributeError):
        return False


def enforce_user_limit(business_id):
    """Check if the business has reached its user limit.

    Returns True if limit is not exceeded, False if limit is reached.
    """
    from models import User

    if business_id is None:
        return True

    sub = get_current_subscription(business_id)
    if not sub:
        return False

    max_users = sub.plan.max_users
    user_count = User.query.filter_by(business_id=business_id, is_active=True).count()
    return user_count < max_users