"""Service functions for bank reconciliation period locks."""

from datetime import date, datetime

from sqlalchemy import select

from models import db
from app.models.accounting import BankReconciliationPeriod, Business, ChartOfAccounts


class ReconciliationPeriodClosedError(Exception):
    """Raised when attempting to reconcile in a locked period."""

    def __init__(self, period_end, account_code=None):
        self.period_end = period_end
        self.account_code = account_code
        msg = f"Bank reconciliation period through {period_end.isoformat()} is locked"
        if account_code:
            msg += f" for account {account_code}"
        msg += "; cannot match or unmatch statements in this period."
        super().__init__(msg)


def _get_account_code(account_id):
    acct = db.session.get(ChartOfAccounts, account_id)
    return acct.code if acct else None


def assert_reconciliation_open(business_id, account_id, statement_date):
    """Raise if a locked reconciliation period covers the statement date.

    Args:
        business_id: Business ID
        account_id: Bank account (ChartOfAccounts) ID
        statement_date: Date of the bank statement (datetime or date)

    Raises:
        ReconciliationPeriodClosedError: If a locked period covers the date.
    """
    if isinstance(statement_date, datetime):
        statement_date = statement_date.date()

    locked = db.session.scalar(
        select(BankReconciliationPeriod).where(
            BankReconciliationPeriod.business_id == business_id,
            BankReconciliationPeriod.account_id == account_id,
            BankReconciliationPeriod.period_end >= statement_date,
            BankReconciliationPeriod.is_locked.is_(True),
        ).order_by(BankReconciliationPeriod.period_end.asc()).limit(1)
    )

    if locked:
        account_code = _get_account_code(account_id)
        raise ReconciliationPeriodClosedError(locked.period_end, account_code)


def close_reconciliation_period(business_id, account_id, period_end, user_id):
    """Lock a reconciliation period for a bank account.

    Args:
        business_id: Business ID
        account_id: Bank account ID
        period_end: End date of the period (typically month-end)
        user_id: User performing the lock

    Returns:
        BankReconciliationPeriod: The created lock record.

    Raises:
        ValueError: If period_end is invalid, in future, or already locked.
    """
    if period_end > date.today():
        raise ValueError("Cannot close a reconciliation period beyond today's date")

    account = db.session.get(ChartOfAccounts, account_id)
    if not account or account.business_id != business_id:
        raise ValueError("Invalid bank account for this business")

    existing = db.session.scalar(
        select(BankReconciliationPeriod).where(
            BankReconciliationPeriod.business_id == business_id,
            BankReconciliationPeriod.account_id == account_id,
            BankReconciliationPeriod.period_end == period_end,
        )
    )
    if existing:
        if existing.is_locked:
            raise ValueError(f"Reconciliation period through {period_end.isoformat()} is already locked")
        existing.is_locked = True
        existing.closed_by = user_id
        existing.closed_at = datetime.now()
        existing.reopened_by = None
        existing.reopened_at = None
        return existing

    locked = BankReconciliationPeriod(
        business_id=business_id,
        account_id=account_id,
        period_end=period_end,
        closed_by=user_id,
        closed_at=datetime.now(),
        is_locked=True,
    )
    db.session.add(locked)
    return locked


def reopen_reconciliation_period(business_id, account_id, period_end, user_id):
    """Reopen (unlock) a previously closed reconciliation period.

    Admin-only operation; the action is audited.

    Args:
        business_id: Business ID
        account_id: Bank account ID
        period_end: Period end date to reopen
        user_id: Admin user performing the reopen

    Returns:
        BankReconciliationPeriod: The updated record with is_locked=False.

    Raises:
        ValueError: If no locked period exists for the given parameters.
    """
    locked = db.session.scalar(
        select(BankReconciliationPeriod).where(
            BankReconciliationPeriod.business_id == business_id,
            BankReconciliationPeriod.account_id == account_id,
            BankReconciliationPeriod.period_end == period_end,
            BankReconciliationPeriod.is_locked.is_(True),
        )
    )
    if not locked:
        raise ValueError(f"No locked reconciliation period found for {period_end.isoformat()}")

    locked.is_locked = False
    locked.reopened_by = user_id
    locked.reopened_at = datetime.now()
    return locked


def get_reconciliation_periods(business_id, account_id=None):
    """Get all reconciliation periods for a business (optionally filtered by account)."""
    query = select(BankReconciliationPeriod).where(
        BankReconciliationPeriod.business_id == business_id
    )
    if account_id:
        query = query.where(BankReconciliationPeriod.account_id == account_id)
    query = query.order_by(
        BankReconciliationPeriod.account_id,
        BankReconciliationPeriod.period_end.desc()
    )
    return db.session.scalars(query).all()