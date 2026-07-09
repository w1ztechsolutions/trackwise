"""AP Aging report derived from journal entries."""

from datetime import datetime, timedelta
from models import db, Supplier, Bill, ChartOfAccounts, JournalLine, JournalEntry


def get_ap_aging(business_id, as_of_date=None):
    """Generate an AP Aging report from journal entries.
    
    Args:
        business_id: The business to generate the report for
        as_of_date: Optional date to calculate aging as of (datetime)
    
    Returns:
        dict with supplier balances grouped by aging buckets
    """
    if as_of_date is None:
        as_of_date = datetime.now()
    
    # Get all suppliers for the business
    suppliers = Supplier.query.filter_by(
        business_id=business_id, is_active=True
    ).all()
    
    # Get AP account
    ap_acct = ChartOfAccounts.query.filter_by(
        business_id=business_id, code='2100', is_active=True
    ).first()
    
    # Get all bills for the business
    bills = Bill.query.filter_by(
        business_id=business_id
    ).all()
    
    # Build supplier aging data
    aging_data = []
    
    for supplier in suppliers:
        # Get bills for this supplier
        supplier_bills = [b for b in bills if b.supplier_id == supplier.id]
        
        # Calculate total outstanding balance
        total_balance = 0.0
        for bill in supplier_bills:
            if bill.status in ('draft', 'received'):
                total_balance += float(bill.total_amount or 0)
        
        if total_balance <= 0:
            continue
        
        # Calculate aging buckets based on due dates
        current = 0.0      # 0-30 days
        days_30 = 0.0      # 31-60 days
        days_60 = 0.0      # 61-90 days
        days_90 = 0.0      # 90+ days
        
        for bill in supplier_bills:
            if bill.status not in ('draft', 'received'):
                continue
            
            # Use due_date if available, otherwise bill_date
            ref_date = bill.due_date or bill.bill_date
            if ref_date is None:
                continue
            
            days_overdue = (as_of_date.date() - ref_date.date()).days
            amount = float(bill.total_amount or 0)
            
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
            'supplier': supplier,
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