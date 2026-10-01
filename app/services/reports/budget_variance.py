"""Generalized budget variance engine for revenue and expense budgets."""

from datetime import date, timedelta
from decimal import Decimal

from app.models import (
    Budget,
    ChartOfAccounts,
    ExpenseBudget,
    db,
)
from app.services.budget_service import (
    COGS_ACCOUNT_CODE,
    BudgetError,
    compute_actuals,
    month_bounds,
)


def _account_query(business_id, budget_type):
    query = ChartOfAccounts.query.filter(
        ChartOfAccounts.business_id == business_id,
        ChartOfAccounts.is_active.is_(True),
    )
    if budget_type == 'revenue':
        return query.filter(ChartOfAccounts.type == 'income').order_by(ChartOfAccounts.code)
    return (
        query
        .filter(ChartOfAccounts.type == 'expense')
        .filter(ChartOfAccounts.code != COGS_ACCOUNT_CODE)
        .order_by(ChartOfAccounts.code)
    )


def _period_end(period_start):
    _, end_at = month_bounds(period_start)
    return end_at.date() - timedelta(days=1)


def _new_budget_amounts(business_id, budget_type, period_start):
    """Sum new-model budget amounts per account for budgets covering the month.

    Returns ``(amounts, covered_account_ids)`` where covered accounts take
    precedence over legacy budget rows for the same account.
    """
    period_end = _period_end(period_start)
    budgets = (
        Budget.query
        .filter(
            Budget.business_id == business_id,
            Budget.budget_type == budget_type,
            Budget.status != 'archived',
            Budget.period_start <= period_end,
            Budget.period_end >= period_start,
        )
        .order_by(Budget.id)
        .all()
    )
    amounts = {}
    covered = set()
    for budget in budgets:
        for line in budget.lines:
            if line.cost_center_id is not None:
                continue
            covered.add(line.account_id)
            amounts[line.account_id] = amounts.get(line.account_id, Decimal('0')) + Decimal(line.amount)
    return amounts, covered


def _legacy_amounts(business_id, period_start, account_ids):
    if not account_ids:
        return {}
    return {
        row.account_id: Decimal(row.amount)
        for row in ExpenseBudget.query.filter(
            ExpenseBudget.business_id == business_id,
            ExpenseBudget.period_start == period_start,
            ExpenseBudget.account_id.in_(account_ids),
        ).all()
    }


def _variance(business_id, budget_type, period_start):
    accounts = _account_query(business_id, budget_type).all()
    account_ids = [account.id for account in accounts]
    if not account_ids:
        return {
            'budget_type': budget_type,
            'period_start': period_start,
            'period_end': _period_end(period_start),
            'accounts': [],
            'rows': [],
            'total_budget': Decimal('0'),
            'total_actual': Decimal('0'),
            'total_variance': Decimal('0'),
        }

    new_amounts, covered = _new_budget_amounts(business_id, budget_type, period_start)
    budgets = _legacy_amounts(business_id, period_start, account_ids)
    budgets.update({account_id: new_amounts[account_id] for account_id in covered})

    actuals = compute_actuals(
        business_id,
        account_ids,
        period_start,
        _period_end(period_start),
    )

    rows = []
    for account in accounts:
        budget = budgets.get(account.id, Decimal('0'))
        actual = actuals.get(account.id, Decimal('0'))
        rows.append({
            'account': account,
            'budget': budget,
            'actual': actual,
            'variance': budget - actual,
            'percent_used': (actual / budget * 100) if budget else None,
        })

    total_budget = sum((row['budget'] for row in rows), Decimal('0'))
    total_actual = sum((row['actual'] for row in rows), Decimal('0'))
    return {
        'budget_type': budget_type,
        'period_start': period_start,
        'period_end': _period_end(period_start),
        'accounts': accounts,
        'rows': rows,
        'total_budget': total_budget,
        'total_actual': total_actual,
        'total_variance': total_budget - total_actual,
    }


def get_expense_budget_variance(business_id, period_start):
    """Return monthly expense budgets and posted operating expenses by account."""
    return _variance(business_id, 'expense', period_start)


def get_revenue_budget_variance(business_id, period_start):
    """Return monthly revenue budgets and posted income by account."""
    return _variance(business_id, 'revenue', period_start)


def get_budget_variance(budget_id):
    """Return the line-level variance for a single budget record."""
    from app.services.budget_service import get_budget_lines

    return get_budget_lines(budget_id)


def get_period_comparison(business_id, account_ids, periods, budget_type='expense'):
    """Compare actual amounts for several periods over the same accounts.

    ``periods`` is a sequence of ``(period_start, period_end)`` inclusive date
    pairs. Returns per-period actuals plus the change between each period and
    the first one supplied.
    """
    if not account_ids:
        raise BudgetError('Select at least one account to compare.')

    results = []
    baseline = None
    for period_start, period_end in periods:
        if not isinstance(period_start, date) or not isinstance(period_end, date):
            raise BudgetError('Comparison periods must be dates.')
        actuals = compute_actuals(business_id, list(account_ids), period_start, period_end)
        total = sum(actuals.values(), Decimal('0'))
        if baseline is None:
            baseline = total
        results.append({
            'period_start': period_start,
            'period_end': period_end,
            'actuals': actuals,
            'total_actual': total,
            'change': total - baseline,
            'percent_change': (
                (total - baseline) / baseline * 100 if baseline else None
            ),
        })

    return {
        'budget_type': budget_type,
        'account_ids': list(account_ids),
        'periods': results,
        'baseline_total': baseline if baseline is not None else Decimal('0'),
    }