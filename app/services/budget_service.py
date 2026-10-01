"""Budget planning, validation, and actual-amount computation."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from app.models import (
    Budget,
    BudgetLineItem,
    ChartOfAccounts,
    JournalEntry,
    JournalLine,
    db,
)

MAX_BUDGET_AMOUNT = Decimal('999999999999.99')
COGS_ACCOUNT_CODE = '5000'


class BudgetError(ValueError):
    """Raised when budget input fails validation."""


def month_bounds(period_start):
    """Return the half-open datetime bounds for a month starting at period_start."""
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


def period_datetime_bounds(period_start, period_end):
    """Return half-open datetime bounds covering an inclusive date range."""
    if not isinstance(period_start, date) or not isinstance(period_end, date):
        raise ValueError('Budget period dates are required.')
    if period_end < period_start:
        raise BudgetError('Budget period must end on or after it starts.')

    start_at = datetime.combine(period_start, time.min)
    end_at = datetime.combine(period_end + timedelta(days=1), time.min)
    return start_at, end_at


def normalize_amount(value, field='Amount'):
    """Parse a budget amount into a non-negative two-decimal Decimal."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise BudgetError(f'{field} must be a valid number.') from error
    if not amount.is_finite():
        raise BudgetError(f'{field} must be a finite number.')
    if amount < 0:
        raise BudgetError(f'{field} cannot be negative.')
    if amount > MAX_BUDGET_AMOUNT:
        raise BudgetError(f'{field} exceeds the maximum supported value.')
    if amount != amount.quantize(Decimal('0.01')):
        raise BudgetError(f'{field} must have no more than two decimal places.')
    return amount


def budget_account_filter(business_id, budget_type):
    """Return a query filter selecting accounts eligible for a budget type."""
    if budget_type == 'revenue':
        return (
            ChartOfAccounts.business_id == business_id,
            ChartOfAccounts.type == 'income',
            ChartOfAccounts.is_active.is_(True),
        )
    return (
        ChartOfAccounts.business_id == business_id,
        ChartOfAccounts.type == 'expense',
        ChartOfAccounts.code != COGS_ACCOUNT_CODE,
        ChartOfAccounts.is_active.is_(True),
    )


def eligible_budget_accounts(business_id, budget_type):
    return (
        ChartOfAccounts.query
        .filter(*budget_account_filter(business_id, budget_type))
        .order_by(ChartOfAccounts.code)
        .all()
    )


def resolve_budget_account(business_id, budget_type, account_id):
    account = ChartOfAccounts.query.filter(
        ChartOfAccounts.id == account_id,
        *budget_account_filter(business_id, budget_type),
    ).first()
    if account is None:
        if budget_type == 'revenue':
            raise BudgetError('Select an active revenue account for this business.')
        raise BudgetError('Select an active operating expense account for this business.')
    return account


def create_budget(
    business_id,
    name,
    budget_type,
    period_start,
    period_end,
    lines,
    created_by=None,
    status='draft',
    commit=True,
):
    """Create a budget with validated line items and return the persisted record."""
    from app.services.period_service import assert_period_open

    if business_id is None:
        raise BudgetError('business_id is required')

    name = (name or '').strip()
    if not name:
        raise BudgetError('Budget name is required.')
    if len(name) > 200:
        raise BudgetError('Budget name must be 200 characters or fewer.')

    if budget_type not in ('revenue', 'expense'):
        raise BudgetError('Budget type must be revenue or expense.')
    if status not in ('draft', 'approved', 'archived'):
        raise BudgetError('Budget status must be draft, approved, or archived.')

    start_at, end_at = period_datetime_bounds(period_start, period_end)
    assert_period_open(business_id, start_at)

    normalized_lines = []
    seen_keys = set()
    for line in lines or []:
        account_id = line.get('account_id')
        try:
            account_id = int(account_id)
        except (TypeError, ValueError) as error:
            raise BudgetError('Each budget line requires an account.') from error

        account = resolve_budget_account(business_id, budget_type, account_id)

        cost_center_id = line.get('cost_center_id')
        if cost_center_id in ('', None):
            cost_center_id = None
        else:
            from app.models import CostCenter

            try:
                cost_center_id = int(cost_center_id)
            except (TypeError, ValueError) as error:
                raise BudgetError('Cost center selection is invalid.') from error
            center = CostCenter.query.filter_by(
                id=cost_center_id,
                business_id=business_id,
            ).first()
            if center is None:
                raise BudgetError('Cost center selection is invalid.')

        key = (account_id, cost_center_id)
        if key in seen_keys:
            raise BudgetError(
                f'{account.code} - {account.name} is budgeted more than once.'
            )
        seen_keys.add(key)

        normalized_lines.append({
            'account': account,
            'cost_center_id': cost_center_id,
            'amount': normalize_amount(line.get('amount'), field=f'Amount for {account.name}'),
            'notes': (line.get('notes') or '').strip() or None,
        })

    if not normalized_lines:
        raise BudgetError('Add at least one budget line.')

    budget = Budget(
        business_id=business_id,
        name=name,
        budget_type=budget_type,
        period_start=period_start,
        period_end=period_end,
        status=status,
        created_by=created_by,
    )
    db.session.add(budget)
    db.session.flush()

    for line in normalized_lines:
        db.session.add(BudgetLineItem(
            budget_id=budget.id,
            account_id=line['account'].id,
            cost_center_id=line['cost_center_id'],
            amount=line['amount'],
            notes=line['notes'],
        ))

    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return budget


def update_budget_amount(budget_id, line_id, amount, commit=True):
    """Update a single budget line amount, keeping the rest of the budget intact."""
    from app.services.period_service import assert_period_open

    budget = db.session.get(Budget, budget_id)
    if budget is None:
        raise BudgetError('Budget not found.')
    assert_period_open(budget.business_id, datetime.combine(budget.period_start, time.min))

    line = db.session.get(BudgetLineItem, line_id)
    if line is None or line.budget_id != budget.id:
        raise BudgetError('Budget line not found.')

    line.amount = normalize_amount(amount)
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return line


def compute_actuals(business_id, account_ids, period_start, period_end, cost_center_id=None):
    """Return signed actual totals per account for a period.

    Expenses report debit minus credit; revenue reports credit minus debit.
    Account type determines the sign so callers can compare like-for-like.
    """
    if not account_ids:
        return {}

    start_at, end_at = period_datetime_bounds(period_start, period_end)
    query = (
        db.session.query(
            JournalLine.account_id,
            db.func.sum(JournalLine.debit_amount).label('debits'),
            db.func.sum(JournalLine.credit_amount).label('credits'),
        )
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .filter(
            JournalEntry.business_id == business_id,
            JournalEntry.is_deleted.is_(False),
            JournalEntry.entry_date >= start_at,
            JournalEntry.entry_date < end_at,
            JournalLine.account_id.in_(account_ids),
        )
    )
    if cost_center_id is not None:
        query = query.filter(JournalLine.cost_center_id == cost_center_id)
    rows = query.group_by(JournalLine.account_id).all()

    account_types = {
        account.id: account.type
        for account in ChartOfAccounts.query.filter(
            ChartOfAccounts.id.in_(account_ids),
            ChartOfAccounts.business_id == business_id,
        ).all()
    }

    actuals = {}
    for row in rows:
        debits = Decimal(row.debits or 0)
        credits = Decimal(row.credits or 0)
        actuals[row.account_id] = (
            credits - debits if account_types.get(row.account_id) == 'income' else debits - credits
        )
    return actuals


def get_budget_lines(budget_id):
    """Return a budget's lines annotated with actuals and variance."""
    budget = db.session.get(Budget, budget_id)
    if budget is None:
        raise BudgetError('Budget not found.')

    lines = sorted(budget.lines, key=lambda line: (line.account.code, line.id))
    if not lines:
        return {
            'budget': budget,
            'rows': [],
            'total_budget': Decimal('0'),
            'total_actual': Decimal('0'),
            'total_variance': Decimal('0'),
        }

    actuals = compute_actuals(
        budget.business_id,
        [line.account_id for line in lines],
        budget.period_start,
        budget.period_end,
    )

    rows = []
    for line in lines:
        budget_amount = Decimal(line.amount)
        actual = actuals.get(line.account_id, Decimal('0'))
        rows.append({
            'line': line,
            'account': line.account,
            'cost_center': line.cost_center,
            'budget': budget_amount,
            'actual': actual,
            'variance': budget_amount - actual,
            'percent_used': (actual / budget_amount * 100) if budget_amount else None,
        })

    total_budget = sum((row['budget'] for row in rows), Decimal('0'))
    total_actual = sum((row['actual'] for row in rows), Decimal('0'))
    return {
        'budget': budget,
        'rows': rows,
        'total_budget': total_budget,
        'total_actual': total_actual,
        'total_variance': total_budget - total_actual,
    }


def list_budgets(business_id, budget_type=None, status=None):
    query = Budget.query.filter(Budget.business_id == business_id)
    if budget_type:
        query = query.filter(Budget.budget_type == budget_type)
    if status:
        query = query.filter(Budget.status == status)
    return query.order_by(Budget.period_start.desc(), Budget.id.desc()).all()


def budgets_for_period(business_id, budget_type, period_start, period_end=None):
    """Return budgets covering a period, used to aggregate dashboard trend data."""
    query = Budget.query.filter(
        Budget.business_id == business_id,
        Budget.budget_type == budget_type,
        Budget.period_start <= (period_end or period_start),
        Budget.period_end >= period_start,
    )
    return query.order_by(Budget.period_start.asc(), Budget.id.asc()).all()


def get_monthly_budget_vs_actual(business_id, period_start):
    """Return per-account budget and actual amounts for a month, by budget type."""
    from app.services.reports.budget_variance import (
        get_expense_budget_variance,
        get_revenue_budget_variance,
    )

    expense = get_expense_budget_variance(business_id, period_start)
    revenue = get_revenue_budget_variance(business_id, period_start)
    return {
        'period_start': period_start,
        'expense': expense,
        'revenue': revenue,
        'total_budget': expense['total_budget'] + revenue['total_budget'],
        'total_actual': expense['total_actual'] + revenue['total_actual'],
    }


def get_dashboard_budget_summary(business_id, period_start, months=6):
    """Return monthly budget totals, actuals, and utilization for dashboard charts."""
    rows = []
    labels = []
    budgets = []
    actuals = []
    utilization = []

    for offset in range(-(months - 1), 1):
        year = period_start.year + (period_start.month - 1 + offset) // 12
        month = (period_start.month - 1 + offset) % 12 + 1
        month_start = date(year, month, 1)
        month_end = (
            date(year + 1, 1, 1) - timedelta(days=1)
            if month == 12
            else date(year, month + 1, 1) - timedelta(days=1)
        )

        period_budgets = budgets_for_period(business_id, 'expense', month_start, month_end)
        budget_total = Decimal('0')
        for budget in period_budgets:
            for line in budget.lines:
                budget_total += Decimal(line.amount)

        start_at, end_at = period_datetime_bounds(month_start, month_end)
        expense_accounts = [
            account.id
            for account in eligible_budget_accounts(business_id, 'expense')
        ]
        month_actuals = compute_actuals(
            business_id,
            expense_accounts,
            month_start,
            month_end,
        )
        actual_total = sum(month_actuals.values(), Decimal('0'))

        labels.append(month_start.strftime('%b %Y'))
        budgets.append(float(budget_total))
        actuals.append(float(actual_total))
        utilization.append(
            round(float(actual_total / budget_total * 100), 1) if budget_total else None
        )
        rows.append({
            'period_start': month_start,
            'budget': budget_total,
            'actual': actual_total,
            'percent_used': (actual_total / budget_total * 100) if budget_total else None,
        })

    return {
        'period_start': period_start,
        'labels': labels,
        'budgets': budgets,
        'actuals': actuals,
        'utilization': utilization,
        'rows': rows,
    }