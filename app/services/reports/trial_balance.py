"""Trial Balance report derived from journal entries."""

from models import db, ChartOfAccounts, JournalLine, JournalEntry


def get_trial_balance(business_id, as_of_date=None):
    """Generate a Trial Balance from journal entries.
    
    Args:
        business_id: The business to generate the report for
        as_of_date: Optional date to calculate balances as of (datetime)
    
    Returns:
        dict with all accounts and their debit/credit totals
    """
    # Get all accounts for the business
    accounts = ChartOfAccounts.query.filter_by(
        business_id=business_id, is_active=True
    ).order_by(ChartOfAccounts.code).all()
    
    # Query journal lines with date filtering
    line_query = db.session.query(
        JournalLine.account_id,
        db.func.sum(JournalLine.debit_amount).label('total_debit'),
        db.func.sum(JournalLine.credit_amount).label('total_credit'),
    ).join(JournalEntry).filter(
        JournalEntry.business_id == business_id
    )
    
    if as_of_date:
        line_query = line_query.filter(JournalEntry.entry_date <= as_of_date)
    
    line_query = line_query.group_by(JournalLine.account_id)
    
    # Get account balances
    account_balances = {}
    for row in line_query.all():
        account_balances[row.account_id] = {
            'debit': float(row.total_debit or 0),
            'credit': float(row.total_credit or 0),
        }
    
    # Build trial balance entries
    entries = []
    total_debits = 0.0
    total_credits = 0.0
    
    for acct in accounts:
        bal = account_balances.get(acct.id, {'debit': 0, 'credit': 0})
        debit = bal['debit']
        credit = bal['credit']
        
        # For trial balance, we show the actual debit/credit amounts
        # Normal balance is determined by account type
        if acct.type in ('asset', 'expense'):
            # Normal debit balance
            balance = debit - credit
        else:
            # Normal credit balance (liability, equity, income)
            balance = credit - debit
        
        entries.append({
            'account': acct,
            'debit': debit,
            'credit': credit,
            'balance': balance,
        })
        
        total_debits += debit
        total_credits += credit
    
    # Verify trial balance
    is_balanced = abs(total_debits - total_credits) < 0.01
    
    return {
        'entries': entries,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'is_balanced': is_balanced,
        'difference': total_debits - total_credits,
        'as_of_date': as_of_date,
    }