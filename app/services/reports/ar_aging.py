"""AR Aging report derived from journal entries."""

from datetime import datetime, timedelta
from models import db, Customer, Invoice, ChartOfAccounts, JournalLine, JournalEntry


def get_ar_aging(business_id, as_of_date=None):
    """Generate an AR Aging report from journal entries.
    
    Args:
        business_id: The business to generate the report for
        as_of_date: Optional date to calculate aging as of (datetime)
    
    Returns:
        dict with customer balances grouped by aging buckets
    """
    if as_of_date is None:
        as_of_date = datetime.now()
    
    # Get all customers for the business
    customers = Customer.query.filter_by(
        business_id=business_id, is_active=True
    ).all()
    
    # Get AR account
    ar_acct = ChartOfAccounts.query.filter_by(
        business_id=business_id, code='1200', is_active=True
    ).first()
    
    # Get all invoices for the business
    invoices = Invoice.query.filter_by(
        business_id=business_id
    ).all()
    
    # Build customer aging data
    aging_data = []
    
    for customer in customers:
        # Get invoices for this customer
        customer_invoices = [i for i in invoices if i.customer_id == customer.id]
        
        # Calculate total outstanding balance
        total_balance = 0.0
        for inv in customer_invoices:
            if inv.status in ('draft', 'issued'):
                total_balance += float(inv.total_amount or 0)
        
        if total_balance <= 0:
            continue
        
        # Calculate aging buckets based on due dates
        current = 0.0      # 0-30 days
        days_30 = 0.0      # 31-60 days
        days_60 = 0.0      # 61-90 days
        days_90 = 0.0      # 90+ days
        
        for inv in customer_invoices:
            if inv.status not in ('draft', 'issued'):
                continue
            
            # Use due_date if available, otherwise invoice_date
            ref_date = inv.due_date or inv.invoice_date
            if ref_date is None:
                continue
            
            days_overdue = (as_of_date.date() - ref_date.date()).days
            amount = float(inv.total_amount or 0)
            
            if days_overdue <= 0:
                current += amount
            elif days_overdue <= 30:
                current += amount
            elif days_overdue <= 60:
                days_30 += amount
            elif days_overdue <= 90:
                days_60 += amount
            else:
                days_90 += amount
        
        # If no due dates, put all in current
        if all(v == 0 for v in [current, days_30, days_60, days_90]) and total_balance > 0:
            current = total_balance
        
        aging_data.append({
            'customer': customer,
            'total_balance': total_balance,
            'current': current,
            'days_30': days_30,
            'days_60': days_60,
            'days_90': days_90,
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