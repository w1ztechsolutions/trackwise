"""Expense budget maintenance and monthly variance reporting."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from app.models import (
    ChartOfAccounts,
    ExpenseBudget,
    JournalEntry,
    JournalLine,
    db,
)


def _month_bounds(period_start):
    if not isinstance(period_start, date) or period_start.day != 1:
        raise ValueError('Budget period must begin on the first day of a month.')

    next_month = (
        date(period_start.year + 1, 1, 1)
        if period_start.month == 12
        else date(period_start.year, period_start.month + 1, 1)
    )
    return (
        datetime.combine(period_start, time.min),
        datetime.combine(next_month, time.min),
    )


def get_expense_budget_variance(business_id, period_start):
    """Return monthly budgets and actual posted operating expenses by account."""
    start_at, end_at = _month_bounds(period_start)
    accounts = (
        ChartOfAccounts.query
        .filter(
            ChartOfAccounts.business_id == business_id,
            ChartOfAccounts.type == 'expense',
            ChartOfAccounts.code != '5000',
            ChartOfAccounts.is_active.is_(True),
        )
        .order_by(ChartOfAccounts.code)
        .all()
    )
    account_ids = [account.id for account in accounts]

    actual_rows = (
        db.session.query(
            JournalLine.account_id,
            db.func.sum(
                JournalLine.debit_amount - JournalLine.credit_amount
            ).label('actual'),
        )
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .filter(
            JournalEntry.business_id == business_id,
            JournalEntry.is_deleted.is_(False),
            JournalEntry.entry_date >= start_at,
            JournalEntry.entry_date < end_at,
            JournalLine.account_id.in_(account_ids),
        )
        .group_by(JournalLine.account_id)
        .all()
    ) if account_ids else []
    actuals = {row.account_id: Decimal(row.actual or 0) for row in actual_rows}

    budgets = {
        budget.account_id: Decimal(budget.amount)
        for budget in ExpenseBudget.query.filter(
            ExpenseBudget.business_id == business_id,
            ExpenseBudget.period_start == period_start,
            ExpenseBudget.account_id.in_(account_ids),
        ).all()
    } if account_ids else {}

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
        'period_start': period_start,
        'period_end': end_at.date() - timedelta(days=1),
        'accounts': accounts,
        'rows': rows,
        'total_budget': total_budget,
        'total_actual': total_actual,
        'total_variance': total_budget - total_actual,
    }


def set_expense_budget(business_id, account_id, period_start, amount, created_by=None):
    """Create or update a monthly budget for an operating expense account."""
    _month_bounds(period_start)
    try:
        budget_amount = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError('Enter a valid budget amount.') from error
    if not budget_amount.is_finite() or budget_amount < 0:
        raise ValueError('Budget amount must be a non-negative number.')
    if budget_amount > Decimal('999999999999.99'):
        raise ValueError('Budget amount exceeds the maximum supported value.')
    if budget_amount != budget_amount.quantize(Decimal('0.01')):
        raise ValueError('Budget amount must have no more than two decimal places.')

    account = ChartOfAccounts.query.filter(
        ChartOfAccounts.id == account_id,
        ChartOfAccounts.business_id == business_id,
        ChartOfAccounts.type == 'expense',
        ChartOfAccounts.code != '5000',
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
