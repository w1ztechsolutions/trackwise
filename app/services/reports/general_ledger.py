"""General Ledger report derived from journal entries."""

from models import db, ChartOfAccounts, JournalLine, JournalEntry


def get_general_ledger(business_id, account_id=None, start_date=None, end_date=None):
    """Generate a General Ledger from journal entries.
    
    Args:
        business_id: The business to generate the report for
        account_id: Optional specific account to filter by
        start_date: Optional start date filter (datetime)
        end_date: Optional end date filter (datetime)
    
    Returns:
        dict with account details and all journal lines
    """
    # Get all accounts for the business
    accounts = ChartOfAccounts.query.filter_by(
        business_id=business_id, is_active=True
    ).order_by(ChartOfAccounts.code).all()
    
    # Query journal lines
    line_query = db.session.query(
        JournalLine,
        JournalEntry,
        ChartOfAccounts,
    ).join(JournalEntry).join(
        ChartOfAccounts, JournalLine.account_id == ChartOfAccounts.id
    ).filter(
        JournalEntry.business_id == business_id
    )
    
    if account_id:
        line_query = line_query.filter(JournalLine.account_id == account_id)
    
    if start_date:
        line_query = line_query.filter(JournalEntry.entry_date >= start_date)
    if end_date:
        line_query = line_query.filter(JournalEntry.entry_date <= end_date)
    
    line_query = line_query.order_by(
        JournalEntry.entry_date.asc(),
        JournalEntry.id.asc(),
        JournalLine.id.asc()
    )
    
    # Build ledger entries
    entries = []
    running_balance = 0.0
    
    for line, entry, acct in line_query.all():
        debit = float(line.debit_amount or 0)
        credit = float(line.credit_amount or 0)
        
        # Calculate running balance based on account type
        if acct.type in ('asset', 'expense'):
            running_balance += debit - credit
        else:
            running_balance += credit - debit
        
        entries.append({
            'date': entry.entry_date,
            'entry_id': entry.id,
            'description': entry.description,
            'reference_type': entry.reference_type,
            'reference_id': entry.reference_id,
            'account': acct,
            'debit': debit,
            'credit': credit,
            'balance': running_balance,
        })
    
    # Get the specific account if filtering
    selected_account = None
    if account_id:
        selected_account = ChartOfAccounts.query.filter_by(
            id=account_id, business_id=business_id
        ).first()
    
    return {
        'entries': entries,
        'accounts': accounts,
        'selected_account': selected_account,
        'start_date': start_date,
        'end_date': end_date,
    }