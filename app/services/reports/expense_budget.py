"""Backward-compatible expense budget maintenance backed by the variance engine.

New budget writes should go through ``app.services.budget_service.create_budget``.
This module keeps the original per-account monthly helper working for the
legacy ``expense_budgets`` table and existing routes.
"""

from app.models import ChartOfAccounts, ExpenseBudget, db
from app.services.budget_service import COGS_ACCOUNT_CODE, month_bounds, normalize_amount
from app.services.reports.budget_variance import (
    get_expense_budget_variance,
    get_revenue_budget_variance,
)

__all__ = [
    'get_expense_budget_variance',
    'get_revenue_budget_variance',
    'set_expense_budget',
]


def set_expense_budget(business_id, account_id, period_start, amount, created_by=None):
    """Create or update a monthly budget for an operating expense account."""
    month_bounds(period_start)
    budget_amount = normalize_amount(amount, field='Budget amount')

    account = ChartOfAccounts.query.filter(
        ChartOfAccounts.id == account_id,
        ChartOfAccounts.business_id == business_id,
        ChartOfAccounts.type == 'expense',
        ChartOfAccounts.code != COGS_ACCOUNT_CODE,
        ChartOfAccounts.is_active.is_(True),
    ).first()
    if account is None:
        raise ValueError('Select an active operating expense account for this business.')

    budget = ExpenseBudget.query.filter_by(
        business_id=business_id,
        account_id=account.id,
        period_start=period_start,
    ).first()
    if budget is None:
        budget = ExpenseBudget(
            business_id=business_id,
            account_id=account.id,
            period_start=period_start,
            created_by=created_by,
        )
        db.session.add(budget)
    budget.amount = budget_amount
    db.session.commit()
    return budget