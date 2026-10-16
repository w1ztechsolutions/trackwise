"""Straight-line time-based deferral and recognition of invoice revenue."""

# REVIEW: Revenue recognition engine supporting ASC 606 / IFRS 15 straight-line time-based deferral and recognition.
# REVIEW: Multi-tenant boundary: All schedules, invoices, and journal entries are strictly scoped by business_id.
# REVIEW: Accounting rationale:
# REVIEW:   1. Deferral: Debit Income / Credit Deferred Revenue Liability.
# REVIEW:   2. Recognition: Debit Deferred Revenue Liability / Credit Earned Income.
# REVIEW: Safety Invariants: Prevents deferring more revenue than posted on the invoice sale entry; uses DB row locking
# REVIEW: (with_for_update) during recognition to avoid concurrent recognition races.

from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
from decimal import InvalidOperation

from models import db, Invoice, Sale
from app.models.accounting import (
    ChartOfAccounts,
    JournalEntry,
    JournalLine,
    RevenueRecognitionSchedule,
)
from app.services.accounting_service import post_entry


CENT = Decimal("0.01")


class RevenueRecognitionError(ValueError):
    pass


# REVIEW: Helper quantizing monetary values to Decimal 0.01 with ROUND_HALF_UP rounding.
def _money(value):
    try:
        result = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise RevenueRecognitionError("Revenue amount must be a valid number") from error
    if not result.is_finite():
        raise RevenueRecognitionError("Revenue amount must be finite")
    return result


# REVIEW: Tenant-scoped lookup validating that revenue and deferred revenue accounts exist and match expected GL types.
def _account_for_schedule(business_id, account_id, expected_type):
    account = ChartOfAccounts.query.filter_by(
        id=account_id,
        business_id=business_id,
        is_active=True,
        type=expected_type,
    ).first()
    if account is None:
        raise RevenueRecognitionError(
            f"Select an active {expected_type} account for this business"
        )
    return account


# REVIEW: Calculates net posted income for an invoice from its Sale entries and Reversals.
# REVIEW: Enforces invariant that schedule creation cannot defer more revenue than was actually posted for that invoice.
def _posted_revenue_for_invoice(business_id, invoice_id, account_id):
    sale_ids = [
        row[0]
        for row in db.session.query(Sale.id).filter(
            Sale.business_id == business_id,
            Sale.invoice_id == invoice_id,
        ).all()
    ]
    if not sale_ids:
        raise RevenueRecognitionError(
            "Record the invoice's sale before creating a revenue schedule"
        )

    original_entry_ids = [
        row[0]
        for row in db.session.query(JournalEntry.id).filter(
            JournalEntry.business_id == business_id,
            JournalEntry.reference_type == "Sale",
            JournalEntry.reference_id.in_(sale_ids),
            JournalEntry.is_deleted.is_(False),
        ).all()
    ]
    if not original_entry_ids:
        raise RevenueRecognitionError(
            "The invoice has no posted sale entry to defer"
        )

    reversal_entry_ids = [
        row[0]
        for row in db.session.query(JournalEntry.id).filter(
            JournalEntry.business_id == business_id,
            JournalEntry.reference_type == "Reversal",
            JournalEntry.reference_id.in_(original_entry_ids),
            JournalEntry.is_deleted.is_(False),
        ).all()
    ]
    entry_ids = original_entry_ids + reversal_entry_ids
    balance = db.session.query(
        db.func.coalesce(
            db.func.sum(JournalLine.credit_amount - JournalLine.debit_amount),
            0,
        )
    ).filter(
        JournalLine.journal_entry_id.in_(entry_ids),
        JournalLine.account_id == account_id,
    ).scalar()
    return _money(balance or 0)


# REVIEW: Creates a revenue recognition schedule for an active invoice, validating dates (start >= today, end >= start),
# REVIEW: verifying revenue <= income posted, and posting the initial revenue deferral journal entry.
def create_revenue_schedule(
    business_id,
    invoice_id,
    revenue_account_id,
    deferred_revenue_account_id,
    amount,
    start_date,
    end_date,
    created_by=None,
):
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise RevenueRecognitionError("Start and end dates are required")
    if start_date < date.today():
        raise RevenueRecognitionError("A revenue schedule cannot start in the past")
    if end_date < start_date:
        raise RevenueRecognitionError("End date must be on or after the start date")

    invoice = Invoice.query.filter_by(
        id=invoice_id,
        business_id=business_id,
    ).first()
    if invoice is None or invoice.status in {"draft", "void"}:
        raise RevenueRecognitionError("An active invoice for this business is required")
    if RevenueRecognitionSchedule.query.filter_by(
        business_id=business_id,
        invoice_id=invoice_id,
    ).first():
        raise RevenueRecognitionError("This invoice already has a revenue schedule")

    revenue_account = _account_for_schedule(
        business_id, revenue_account_id, "income"
    )
    deferred_account = _account_for_schedule(
        business_id, deferred_revenue_account_id, "liability"
    )
    amount = _money(amount)
    if amount <= 0:
        raise RevenueRecognitionError("Deferred revenue must be greater than zero")

    available_revenue = _posted_revenue_for_invoice(
        business_id, invoice_id, revenue_account.id
    )
    if amount > available_revenue:
        raise RevenueRecognitionError(
            "Deferred amount exceeds revenue currently posted for this invoice "
            f"({available_revenue:.2f})"
        )

    schedule = RevenueRecognitionSchedule(
        business_id=business_id,
        invoice_id=invoice_id,
        revenue_account_id=revenue_account.id,
        deferred_revenue_account_id=deferred_account.id,
        start_date=start_date,
        end_date=end_date,
        total_amount=amount,
        recognized_amount=Decimal("0.00"),
        status="active",
        created_by=created_by,
    )
    db.session.add(schedule)
    db.session.flush()
    post_entry(
        business_id,
        datetime.now(timezone.utc),
        f"Defer revenue for invoice {invoice.invoice_number or invoice.id}",
        [
            {
                "account_id": revenue_account.id,
                "debit_amount": float(amount),
                "credit_amount": 0,
            },
            {
                "account_id": deferred_account.id,
                "debit_amount": 0,
                "credit_amount": float(amount),
            },
        ],
        reference_type="RevenueDeferral",
        reference_id=schedule.id,
        created_by=created_by,
        commit=False,
    )
    db.session.commit()
    return schedule


# REVIEW: Pro-rata straight-line revenue recognition handler. Acquires row lock via with_for_update(),
# REVIEW: computes earned revenue based on elapsed days, posts the recognition journal entry, and marks complete
# REVIEW: when schedule end date is reached (absorbing rounding cents on the final period).
def recognize_revenue(schedule_id, business_id, through_date, created_by=None):
    if not isinstance(through_date, date):
        raise RevenueRecognitionError("A recognition-through date is required")
    if through_date > date.today():
        raise RevenueRecognitionError("Revenue cannot be recognized in the future")

    schedule = (
        RevenueRecognitionSchedule.query
        .filter_by(id=schedule_id, business_id=business_id)
        .with_for_update()
        .first()
    )
    if schedule is None:
        raise RevenueRecognitionError("Revenue schedule not found")
    if schedule.status != "active":
        raise RevenueRecognitionError("Revenue schedule is already complete")

    target_date = min(through_date, schedule.end_date)
    if target_date < schedule.start_date:
        return None
    if schedule.last_recognized_through and target_date <= schedule.last_recognized_through:
        return None

    total = _money(schedule.total_amount)
    days_total = Decimal((schedule.end_date - schedule.start_date).days + 1)
    days_elapsed = Decimal((target_date - schedule.start_date).days + 1)
    target_recognized = (
        total
        if target_date == schedule.end_date
        else (total * days_elapsed / days_total).quantize(
            CENT,
            rounding=ROUND_HALF_UP,
        )
    )
    amount = target_recognized - _money(schedule.recognized_amount)
    if amount <= 0:
        return None

    entry = post_entry(
        business_id,
        datetime.combine(target_date, time(12), tzinfo=timezone.utc),
        f"Revenue recognition for invoice "
        f"{schedule.invoice.invoice_number or schedule.invoice_id}",
        [
            {
                "account_id": schedule.deferred_revenue_account_id,
                "debit_amount": float(amount),
                "credit_amount": 0,
            },
            {
                "account_id": schedule.revenue_account_id,
                "debit_amount": 0,
                "credit_amount": float(amount),
            },
        ],
        reference_type="RevenueRecognition",
        reference_id=schedule.id,
        created_by=created_by,
        commit=False,
    )
    schedule.recognized_amount = target_recognized
    schedule.last_recognized_through = target_date
    if target_recognized == total:
        schedule.status = "completed"
    db.session.commit()
    return entry
