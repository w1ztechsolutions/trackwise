"""Accounts payable aging based on bill balances, payments, and expenditure returns."""

from decimal import Decimal

from app.models import Bill, Payment, PurchaseReturn, Supplier, db
from app.services.reports.aging_utils import (
    add_to_aging_buckets,
    get_allocated_amounts,
    normalize_as_of_date,
)


def get_returned_amounts(business_id, as_of_date=None):
    """Sum non-reversed expenditure returns per bill, bounded by the bill total.

    Expenditure returns (bill credit notes and cash refunds) reduce what the
    business still owes each supplier, so they are subtracted from the bill
    balance before aging buckets are computed.
    """
    query = (
        db.session.query(PurchaseReturn.bill_id, db.func.sum(PurchaseReturn.amount))
        .filter(
            PurchaseReturn.business_id == business_id,
            PurchaseReturn.is_reversed.is_(False),
            PurchaseReturn.bill_id.isnot(None),
        )
    )
    if as_of_date is not None:
        query = query.filter(PurchaseReturn.return_date <= as_of_date)

    rows = query.group_by(PurchaseReturn.bill_id).all()

    totals = {bill_id: Decimal(amount or 0) for bill_id, amount in rows}
    for bill in (
        Bill.query
        .filter(Bill.business_id == business_id, Bill.id.in_(list(totals)))
        .all()
    ):
        totals[bill.id] = min(totals[bill.id], Decimal(bill.total_amount or 0))
    return totals


def get_ap_aging(business_id, as_of_date=None):
    """Generate an AP Aging report from bills, approved payments, and returns.

    Args:
        business_id: The business to generate the report for
        as_of_date: Optional date to calculate aging as of (datetime)

    Returns:
        dict with supplier balances grouped by aging buckets
    """
    as_of_date = normalize_as_of_date(as_of_date)

    # Get all suppliers for the business
    suppliers = Supplier.query.filter_by(
        business_id=business_id, is_active=True
    ).all()

    bills = Bill.query.filter_by(business_id=business_id).all()
    payments_by_bill = get_allocated_amounts(
        Payment,
        Payment.bill_id,
        Payment.payment_date,
        business_id,
        as_of_date,
        require_approved=True,
    )
    returns_by_bill = get_returned_amounts(business_id, as_of_date)

    # Build supplier aging data
    aging_data = []

    for supplier in suppliers:
        # Get bills for this supplier
        supplier_bills = [
            bill for bill in bills
            if bill.supplier_id == supplier.id and bill.status == "received"
        ]

        # Calculate total outstanding balance
        total_balance = 0.0
        bill_balances = {}
        for bill in supplier_bills:
            outstanding = max(
                float(bill.total_amount or 0)
                - payments_by_bill.get(bill.id, 0.0)
                - float(returns_by_bill.get(bill.id, 0) or 0),
                0.0,
            )
            if outstanding > 0:
                bill_balances[bill.id] = outstanding
                total_balance += outstanding

        if total_balance <= 0:
            continue

        # Calculate aging buckets based on due dates
        buckets = {
            "current": 0.0,
            "days_30": 0.0,
            "days_60": 0.0,
            "days_90": 0.0,
        }

        for bill in supplier_bills:
            add_to_aging_buckets(
                buckets,
                bill.due_date or bill.bill_date,
                as_of_date,
                bill_balances.get(bill.id, 0.0),
            )

        aging_data.append({
            'supplier': supplier,
            'total_balance': total_balance,
            **buckets,
        })

    # Calculate totals
    totals = {
        'total_balance': sum(a['total_balance'] for a in aging_data),
        'current': sum(a['current'] for a in aging_data),
        'days_30': sum(a['days_30'] for a in aging_data),
        'days_60': sum(a['days_60'] for a in aging_data),
        'days_90': sum(a['days_90'] for a in aging_data),
    }

    return {
        'aging_data': aging_data,
        'totals': totals,
        'as_of_date': as_of_date,
        'total_returns': float(sum(returns_by_bill.values(), Decimal('0'))),
    }