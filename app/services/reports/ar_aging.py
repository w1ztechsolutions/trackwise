"""Accounts receivable aging based on invoice balances and linked receipts."""

from app.models import Customer, Invoice, Receipt
from app.services.reports.aging_utils import (
    add_to_aging_buckets,
    get_allocated_amounts,
    normalize_as_of_date,
)


def get_ar_aging(business_id, as_of_date=None):
    """Generate an AR Aging report from journal entries.
    
    Args:
        business_id: The business to generate the report for
        as_of_date: Optional date to calculate aging as of (datetime)
    
    Returns:
        dict with customer balances grouped by aging buckets
    """
    as_of_date = normalize_as_of_date(as_of_date)
    
    # Get all customers for the business
    customers = Customer.query.filter_by(
        business_id=business_id, is_active=True
    ).all()
    
    invoices = Invoice.query.filter_by(business_id=business_id).all()
    receipts_by_invoice = get_allocated_amounts(
        Receipt,
        Receipt.invoice_id,
        Receipt.receipt_date,
        business_id,
        as_of_date,
    )
    
    # Build customer aging data
    aging_data = []
    
    for customer in customers:
        # Get invoices for this customer
        customer_invoices = [
            invoice for invoice in invoices
            if invoice.customer_id == customer.id
            and invoice.status not in ("draft", "void")
        ]
        
        # Calculate total outstanding balance
        total_balance = 0.0
        invoice_balances = {}
        for invoice in customer_invoices:
            outstanding = max(
                float(invoice.total_amount or 0)
                - receipts_by_invoice.get(invoice.id, 0.0),
                0.0,
            )
            if outstanding > 0:
                invoice_balances[invoice.id] = outstanding
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
        
        for invoice in customer_invoices:
            add_to_aging_buckets(
                buckets,
                invoice.due_date or invoice.invoice_date,
                as_of_date,
                invoice_balances.get(invoice.id, 0.0),
            )
        
        aging_data.append({
            'customer': customer,
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
    }