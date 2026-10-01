import math
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.models import (
    db,
    Branch,
    ChartOfAccounts,
    CostCenter,
    JournalEntry,
    JournalLine,
)
from app.services.period_service import assert_period_open


class AccountingException(Exception):
    pass


def post_entry(
    business_id,
    entry_date,
    description,
    lines,
    reference_type=None,
    reference_id=None,
    created_by=None,
    commit=True,
    branch_id=None,
    allow_inactive_dimensions=False,
):
    if business_id is None:
        raise AccountingException("business_id is required")
    assert_period_open(business_id, entry_date or datetime.now(timezone.utc))
    if not lines:
        raise AccountingException("Journal entry must have at least two lines")

    if branch_id in ("", None):
        branch_id = None
    else:
        try:
            branch_id = int(branch_id)
        except (TypeError, ValueError):
            raise AccountingException("Branch selection is invalid")
        branch_filters = {
            'id': branch_id,
            'business_id': business_id,
        }
        if not allow_inactive_dimensions:
            branch_filters['is_active'] = True
        branch = Branch.query.filter_by(**branch_filters).first()
        if branch is None:
            raise AccountingException("Branch not found or inactive")

    normalized_lines = []
    for line in lines:
        if not isinstance(line, dict) or 'account_id' not in line:
            raise AccountingException("Each journal line must specify an account")
        try:
            debit = float(line.get('debit_amount', 0) or 0)
            credit = float(line.get('credit_amount', 0) or 0)
        except (TypeError, ValueError):
            raise AccountingException("Journal line amounts must be numeric")
        if not math.isfinite(debit) or not math.isfinite(credit) or debit < 0 or credit < 0:
            raise AccountingException("Journal line amounts must be finite and non-negative")
        if debit > 0 and credit > 0:
            raise AccountingException("A journal line cannot contain both a debit and a credit")
        if debit > 0 or credit > 0:
            cost_center_id = line.get('cost_center_id')
            if cost_center_id in ("", None):
                cost_center_id = None
            else:
                try:
                    cost_center_id = int(cost_center_id)
                except (TypeError, ValueError):
                    raise AccountingException("Cost center selection is invalid")
            normalized_lines.append({
                'account_id': line['account_id'],
                'debit_amount': debit,
                'credit_amount': credit,
                'cost_center_id': cost_center_id,
            })
    if len(normalized_lines) < 2:
        raise AccountingException("Journal entry must have at least two non-zero lines")

    total_debit = sum(line['debit_amount'] for line in normalized_lines)
    total_credit = sum(line['credit_amount'] for line in normalized_lines)

    if abs(total_debit - total_credit) > 0.01:
        raise AccountingException(
            f"Entry does not balance: debits={total_debit}, credits={total_credit}"
        )

    account_ids = [line['account_id'] for line in normalized_lines]
    accounts = ChartOfAccounts.query.filter(
        ChartOfAccounts.id.in_(account_ids),
        ChartOfAccounts.business_id == business_id,
        ChartOfAccounts.is_active == True,
    ).all()
    found_ids = {a.id for a in accounts}
    missing = set(account_ids) - found_ids
    if missing:
        raise AccountingException(f"Account(s) not found or inactive: {missing}")

    cost_center_ids = {
        line['cost_center_id']
        for line in normalized_lines
        if line['cost_center_id'] is not None
    }
    if cost_center_ids:
        center_query = CostCenter.query.filter(
            CostCenter.id.in_(cost_center_ids),
            CostCenter.business_id == business_id,
        )
        if not allow_inactive_dimensions:
            center_query = center_query.filter(CostCenter.is_active.is_(True))
        centers = center_query.all()
        found_center_ids = {center.id for center in centers}
        missing_centers = cost_center_ids - found_center_ids
        if missing_centers:
            raise AccountingException(
                f"Cost center(s) not found or inactive: {missing_centers}"
            )

    entry = JournalEntry(
        business_id=business_id,
        branch_id=branch_id,
        entry_date=entry_date or datetime.now(timezone.utc),
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
        created_by=created_by,
    )
    db.session.add(entry)
    db.session.flush()

    for line_data in normalized_lines:
        line = JournalLine(
            journal_entry_id=entry.id,
            account_id=line_data['account_id'],
            cost_center_id=line_data['cost_center_id'],
            debit_amount=line_data['debit_amount'],
            credit_amount=line_data['credit_amount'],
        )
        db.session.add(line)

    if commit:
        db.session.commit()
    return entry


def reverse_entry(business_id, entry_id, reason, created_by=None, reversal_date=None):
    """Post a balanced opposite entry while preserving the original posted entry."""
    reason = (reason or "").strip()
    if not reason:
        raise AccountingException("A reason is required to reverse a journal entry")
    if len(reason) > 255:
        raise AccountingException("Reversal reason must be 255 characters or fewer")

    entry = (
        JournalEntry.query
        .filter_by(id=entry_id, business_id=business_id)
        .with_for_update()
        .first()
    )
    if entry is None or entry.is_deleted:
        raise AccountingException("Journal entry not found")
    if entry.reversed_by_entry_id is not None:
        raise AccountingException("Journal entry has already been reversed")
    if not entry.lines:
        raise AccountingException("Journal entry has no lines to reverse")

    reversed_lines = [
        {
            "account_id": line.account_id,
            "debit_amount": line.credit_amount,
            "credit_amount": line.debit_amount,
            "cost_center_id": line.cost_center_id,
        }
        for line in entry.lines
    ]
    reversal = post_entry(
        business_id,
        reversal_date or datetime.now(timezone.utc),
        f"Reversal of journal entry #{entry.id}: {reason}",
        reversed_lines,
        reference_type="Reversal",
        reference_id=entry.id,
        created_by=created_by,
        commit=False,
        branch_id=entry.branch_id,
        allow_inactive_dimensions=True,
    )
    entry.reversed_by_entry_id = reversal.id
    entry.reversal_reason = reason
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise AccountingException("Journal entry has already been reversed") from error
    return reversal


def get_payment_refunded_amount(business_id, payment_id):
    """Sum reversal journal entries already posted against a payment."""
    entries = (
        JournalEntry.query
        .join(JournalLine)
        .filter(
            JournalEntry.business_id == business_id,
            JournalEntry.reference_type == 'PaymentReversal',
            JournalEntry.reference_id == payment_id,
            JournalEntry.is_deleted.is_(False),
        )
        .distinct()
        .all()
    )
    total = 0.0
    for entry in entries:
        for line in entry.lines:
            if line.account and line.account.type == 'asset' and line.account.code == '1000':
                total += float(line.debit_amount or 0)
    return total


def reverse_payment(business_id, payment_id, reason, created_by=None, reversal_date=None, amount=None):
    """Reverse a payment's journal entry, in full or in part.

    A full reversal uses :func:`reverse_entry` so the original entry keeps its
    linked reversal. A partial reversal posts a proportional opposite entry
    against the same accounts.
    """
    from models import Payment

    reason = (reason or "").strip()
    if not reason:
        raise AccountingException("A reason is required to reverse a payment")
    if len(reason) > 255:
        raise AccountingException("Reversal reason must be 255 characters or fewer")

    payment = db.session.get(Payment, payment_id)
    if payment is None or payment.business_id != business_id:
        raise AccountingException("Payment not found")
    if payment.status != 'approved':
        raise AccountingException("Only approved payments can be refunded")
    if payment.is_reversed:
        raise AccountingException("Payment has already been refunded")

    entry = (
        JournalEntry.query
        .filter_by(
            business_id=business_id,
            reference_type='Payment',
            reference_id=payment_id,
        )
        .filter(JournalEntry.is_deleted.is_(False))
        .order_by(JournalEntry.id.desc())
        .first()
    )
    if entry is None:
        raise AccountingException("Payment has no journal entry to refund")

    payment_amount = float(payment.amount or 0)
    already_refunded = get_payment_refunded_amount(business_id, payment_id)
    remaining = round(payment_amount - already_refunded, 2)

    # Omitting the amount refunds whatever balance is left.
    refund_amount = remaining if amount is None else round(float(amount), 2)
    if refund_amount <= 0:
        raise AccountingException("Refund amount must be greater than zero")
    if refund_amount - remaining > 0.01:
        raise AccountingException(
            f"Refund amount exceeds the remaining refundable balance of {remaining:.2f}"
        )

    if already_refunded <= 0.01 and refund_amount + 0.01 >= payment_amount:
        reversal = reverse_entry(
            business_id,
            entry.id,
            reason,
            created_by=created_by,
            reversal_date=reversal_date,
        )
        payment.is_reversed = True
        payment.reversal_reason = reason
        payment.reversal_date = reversal_date or datetime.now(timezone.utc)
        try:
            db.session.commit()
        except IntegrityError as error:
            db.session.rollback()
            raise AccountingException("Payment has already been refunded") from error
        return reversal

    ratio = refund_amount / payment_amount if payment_amount else 0
    reversal_lines = []
    for line in entry.lines:
        debit = float(line.debit_amount or 0) * ratio
        credit = float(line.credit_amount or 0) * ratio
        if debit or credit:
            reversal_lines.append({
                "account_id": line.account_id,
                "debit_amount": round(credit, 2),
                "credit_amount": round(debit, 2),
                "cost_center_id": line.cost_center_id,
            })

    try:
        reversal = post_entry(
            business_id,
            reversal_date or datetime.now(timezone.utc),
            f"Partial refund of payment #{payment.id}: {reason}",
            reversal_lines,
            reference_type='PaymentReversal',
            reference_id=payment.id,
            created_by=created_by,
            commit=False,
            branch_id=entry.branch_id,
            allow_inactive_dimensions=True,
        )
    except AccountingException:
        db.session.rollback()
        raise

    payment.reversal_reason = reason
    payment.reversal_date = reversal_date or datetime.now(timezone.utc)
    if already_refunded + refund_amount >= payment_amount - 0.01:
        payment.is_reversed = True
    db.session.commit()
    return reversal


def get_ledger_balances(business_id, account_ids=None):
    line_sums = db.session.query(
        JournalLine.account_id,
        db.func.sum(JournalLine.debit_amount).label('total_debit'),
        db.func.sum(JournalLine.credit_amount).label('total_credit'),
    ).join(JournalEntry).filter(
        JournalEntry.business_id == business_id,
        JournalEntry.is_deleted.is_(False),
    )

    if account_ids:
        line_sums = line_sums.filter(JournalLine.account_id.in_(account_ids))

    line_sums = line_sums.group_by(JournalLine.account_id).subquery()

    results = db.session.query(
        ChartOfAccounts,
        line_sums.c.total_debit,
        line_sums.c.total_credit,
    ).outerjoin(
        line_sums, ChartOfAccounts.id == line_sums.c.account_id
    ).filter(ChartOfAccounts.business_id == business_id).all()

    balances = []
    for account, total_debit, total_credit in results:
        debit = float(total_debit or 0.0)
        credit = float(total_credit or 0.0)
        balance = debit - credit
        balances.append({
            'account': account,
            'debit': debit,
            'credit': credit,
            'balance': balance,
        })

    return balances


def get_account_by_code(business_id, code):
    return ChartOfAccounts.query.filter_by(
        business_id=business_id, code=code, is_active=True
    ).first()


def post_opening_balance(business_id, account_id, amount, created_by=None):
    """Post a balanced opening-balance entry for a single account.

    The target account is debited (asset/expense) or credited (liability/income/equity)
    on its normal side. The offsetting leg posts to an equity account
    (Capital '3000', falling back to Retained Earnings '3100'), keeping the
    entry in balance per double-entry rules.
    """
    if business_id is None:
        raise AccountingException("business_id is required")
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise AccountingException("Opening balance amount must be numeric")
    if amount <= 0:
        raise AccountingException("Opening balance amount must be greater than zero")

    account = db.session.get(ChartOfAccounts, account_id)
    if not account or account.business_id != business_id or not account.is_active:
        raise AccountingException("Account not found or inactive")

    equity = (
        ChartOfAccounts.query.filter(
            ChartOfAccounts.business_id == business_id,
            ChartOfAccounts.is_active == True,
            ChartOfAccounts.code.in_(("3000", "3100")),
        )
        .order_by(ChartOfAccounts.code)
        .first()
    )
    if not equity:
        raise AccountingException(
            "No equity account (Capital 3000 / Retained Earnings 3100) found to balance the entry"
        )

    if account.type in ("asset", "expense"):
        debit_account, credit_account = account, equity
    else:
        debit_account, credit_account = equity, account

    lines = [
        {"account_id": debit_account.id, "debit_amount": amount, "credit_amount": 0},
        {"account_id": credit_account.id, "debit_amount": 0, "credit_amount": amount},
    ]
    return post_entry(
        business_id,
        datetime.now(timezone.utc),
        f"Opening balance for {account.name} ({account.code})",
        lines,
        reference_type="OpeningBalance",
        reference_id=account.id,
        created_by=created_by,
    )


def verify_balances(business_id):
    line_sums = db.session.query(
        JournalLine.journal_entry_id,
        db.func.sum(JournalLine.debit_amount).label('total_debit'),
        db.func.sum(JournalLine.credit_amount).label('total_credit'),
    ).join(JournalEntry).filter(
        JournalEntry.business_id == business_id,
        JournalEntry.is_deleted.is_(False),
    )
    line_sums = line_sums.group_by(JournalLine.journal_entry_id).subquery()

    results = db.session.query(
        JournalEntry,
        line_sums.c.total_debit,
        line_sums.c.total_credit,
    ).outerjoin(
        line_sums, JournalEntry.id == line_sums.c.journal_entry_id
    ).filter(JournalEntry.business_id == business_id).all()

    balanced = []
    unbalanced = []
    for entry, total_debit, total_credit in results:
        d = float(total_debit or 0.0)
        c = float(total_credit or 0.0)
        if abs(d - c) > 0.01:
            unbalanced.append({
                'entry_id': entry.id,
                'description': entry.description,
                'debits': d,
                'credits': c,
                'difference': d - c,
            })
        else:
            balanced.append({
                'entry_id': entry.id,
                'description': entry.description,
                'amount': d,
            })

    return {
        'business_id': business_id,
        'balanced_count': len(balanced),
        'unbalanced_count': len(unbalanced),
        'unbalanced': unbalanced,
        'balanced': balanced,
    }
