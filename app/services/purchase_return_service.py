"""Expenditure returns: purchase returns, bill credit notes, and cash refunds."""

from datetime import date, datetime, timezone
from decimal import Decimal

from app.models import PurchaseReturn, db
from app.services.accounting_service import (
    AccountingException,
    get_account_by_code,
    post_entry,
    reverse_entry,
)
from app.services.period_service import assert_period_open
from models import Bill, Payment

ACCOUNT_CODE_AP = '2100'
ACCOUNT_CODE_CASH = '1000'
DEFAULT_RETURN_EXPENSE_ACCOUNT = '5900'

RETURN_TYPES = ('credit_note', 'refund')

MAX_RETURN_AMOUNT = Decimal('999999999999.99')


class PurchaseReturnError(ValueError):
    """Raised when a purchase return fails validation."""


def _normalize_amount(value):
    try:
        amount = Decimal(str(value))
    except Exception as error:  # noqa: BLE001 - normalize any parse failure
        raise PurchaseReturnError('Enter a valid return amount.') from error
    if not amount.is_finite():
        raise PurchaseReturnError('Enter a valid return amount.')
    if amount <= 0:
        raise PurchaseReturnError('Return amount must be greater than zero.')
    if amount > MAX_RETURN_AMOUNT:
        raise PurchaseReturnError('Return amount exceeds the maximum supported value.')
    if amount != amount.quantize(Decimal('0.01')):
        raise PurchaseReturnError('Return amount must have no more than two decimal places.')
    return amount


def get_bill_paid_amount(bill_id, as_of=None):
    """Sum approved payments allocated to a bill."""
    query = Payment.query.filter(
        Payment.bill_id == bill_id,
        Payment.status == 'approved',
    )
    if as_of is not None:
        query = query.filter(Payment.payment_date <= as_of)
    return sum((Decimal(payment.amount or 0) for payment in query.all()), Decimal('0'))


def get_returned_amount(bill_id, as_of=None):
    """Sum non-reversed purchase returns applied against a bill."""
    query = PurchaseReturn.query.filter(
        PurchaseReturn.bill_id == bill_id,
        PurchaseReturn.is_reversed.is_(False),
    )
    if as_of is not None:
        query = query.filter(PurchaseReturn.return_date <= as_of)
    return sum((Decimal(item.amount or 0) for item in query.all()), Decimal('0'))


def get_bill_returnable_balance(bill_id, as_of=None):
    """Return the amount of a bill still available to return."""
    bill = db.session.get(Bill, bill_id)
    if bill is None:
        raise PurchaseReturnError('Bill not found.')

    total = Decimal(bill.total_amount or 0)
    paid = get_bill_paid_amount(bill_id, as_of)
    returned = get_returned_amount(bill_id, as_of)
    return max(total - paid - returned, Decimal('0'))


def returnable_bills(business_id):
    """Return received bills with a remaining returnable balance."""
    bills = (
        Bill.query
        .filter(Bill.business_id == business_id, Bill.status == 'received')
        .order_by(Bill.bill_date.desc(), Bill.id.desc())
        .all()
    )
    result = []
    for bill in bills:
        balance = get_bill_returnable_balance(bill.id)
        if balance > 0:
            result.append({
                'bill': bill,
                'returnable': balance,
            })
    return result


def process_purchase_return(
    business_id,
    bill_id,
    amount,
    reason,
    return_type='credit_note',
    created_by=None,
    return_date=None,
    expense_account_code=None,
    commit=True,
):
    """Record a purchase return and post the reversing journal entry.

    Credit notes debit Accounts Payable and credit the expense account.
    Cash refunds debit Accounts Payable and credit Cash.
    """
    if business_id is None:
        raise PurchaseReturnError('business_id is required')

    if return_type not in RETURN_TYPES:
        raise PurchaseReturnError('Return type must be credit_note or refund.')

    reason = (reason or '').strip()
    if not reason:
        raise PurchaseReturnError('A reason is required for an expenditure return.')

    bill = db.session.get(Bill, bill_id) if bill_id else None
    if bill is None or bill.business_id != business_id:
        raise PurchaseReturnError('Select a valid bill for this business.')

    amount_value = _normalize_amount(amount)
    returnable = get_bill_returnable_balance(bill.id)
    if amount_value > returnable:
        raise PurchaseReturnError(
            f'Return amount exceeds the remaining returnable balance of {returnable}.'
        )

    return_date = return_date or datetime.now(timezone.utc)
    if isinstance(return_date, date) and not isinstance(return_date, datetime):
        return_date = datetime.combine(return_date, datetime.min.time())
    assert_period_open(business_id, return_date)

    purchase_return = PurchaseReturn(
        business_id=business_id,
        bill_id=bill.id,
        supplier_id=bill.supplier_id,
        return_date=return_date,
        amount=amount_value,
        reason=reason,
        return_type=return_type,
        is_applied_to_ap=True,
        created_by=created_by,
    )
    db.session.add(purchase_return)
    db.session.flush()

    ap_account = get_account_by_code(business_id, ACCOUNT_CODE_AP)
    if ap_account is None:
        raise PurchaseReturnError(
            'Accounts Payable (2100) is required to process expenditure returns.'
        )

    credit_account_code = (
        ACCOUNT_CODE_CASH
        if return_type == 'refund'
        else (expense_account_code or DEFAULT_RETURN_EXPENSE_ACCOUNT)
    )
    credit_account = get_account_by_code(business_id, credit_account_code)
    if credit_account is None:
        raise PurchaseReturnError(
            f'Account {credit_account_code} is required to process this return.'
        )

    description = (
        f"{'Bill credit note' if return_type == 'credit_note' else 'Cash refund'} "
        f"#{purchase_return.id} for bill {bill.bill_number or bill.id}: {reason}"
    )
    try:
        entry = post_entry(
            business_id,
            return_date,
            description,
            [
                {'account_id': ap_account.id, 'debit_amount': float(amount_value), 'credit_amount': 0},
                {'account_id': credit_account.id, 'debit_amount': 0, 'credit_amount': float(amount_value)},
            ],
            reference_type='PurchaseReturn',
            reference_id=purchase_return.id,
            created_by=created_by,
            commit=False,
        )
    except AccountingException as error:
        db.session.rollback()
        raise PurchaseReturnError(str(error)) from error

    purchase_return.journal_entry_id = entry.id

    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return purchase_return


def reverse_purchase_return(business_id, return_id, reason, created_by=None, reversal_date=None):
    """Reverse a posted purchase return by reversing its journal entry."""
    purchase_return = db.session.get(PurchaseReturn, return_id)
    if purchase_return is None or purchase_return.business_id != business_id:
        raise PurchaseReturnError('Expenditure return not found.')
    if purchase_return.is_reversed:
        raise PurchaseReturnError('This expenditure return has already been reversed.')
    if not purchase_return.journal_entry_id:
        raise PurchaseReturnError('This expenditure return has no journal entry to reverse.')

    try:
        reverse_entry(
            business_id,
            purchase_return.journal_entry_id,
            reason,
            created_by=created_by,
            reversal_date=reversal_date,
        )
    except AccountingException as error:
        db.session.rollback()
        raise PurchaseReturnError(str(error)) from error

    purchase_return.is_reversed = True
    db.session.commit()
    return purchase_return


def get_purchase_return_by_id(business_id, return_id):
    purchase_return = PurchaseReturn.query.filter_by(
        id=return_id,
        business_id=business_id,
    ).first()
    if purchase_return is None:
        raise PurchaseReturnError('Expenditure return not found.')
    return purchase_return


def get_expenditure_returns(
    business_id,
    start_date=None,
    end_date=None,
    supplier_id=None,
    return_type=None,
):
    """Return expenditure returns filtered by date range, supplier, and type."""
    query = PurchaseReturn.query.filter(PurchaseReturn.business_id == business_id)

    if start_date is not None:
        query = query.filter(PurchaseReturn.return_date >= _as_datetime(start_date))
    if end_date is not None:
        query = query.filter(PurchaseReturn.return_date <= _as_datetime(end_date, end=True))
    if supplier_id is not None:
        query = query.filter(PurchaseReturn.supplier_id == supplier_id)
    if return_type:
        query = query.filter(PurchaseReturn.return_type == return_type)

    items = query.order_by(PurchaseReturn.return_date.desc(), PurchaseReturn.id.desc()).all()
    return {
        'items': items,
        'total_amount': sum((Decimal(item.amount or 0) for item in items), Decimal('0')),
        'total_credit_notes': sum(
            (Decimal(item.amount or 0) for item in items if item.return_type == 'credit_note'),
            Decimal('0'),
        ),
        'total_refunds': sum(
            (Decimal(item.amount or 0) for item in items if item.return_type == 'refund'),
            Decimal('0'),
        ),
    }


def _as_datetime(value, end=False):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.max.time() if end else datetime.min.time())
    raise PurchaseReturnError('Enter a valid date.')


def get_supplier(business_id, supplier_id):
    from models import Supplier

    supplier = db.session.get(Supplier, supplier_id)
    if supplier is None or supplier.business_id != business_id:
        return None
    return supplier


__all__ = [
    'PurchaseReturnError',
    'process_purchase_return',
    'reverse_purchase_return',
    'get_purchase_return_by_id',
    'get_expenditure_returns',
    'get_bill_returnable_balance',
    'get_bill_paid_amount',
    'get_returned_amount',
    'returnable_bills',
]