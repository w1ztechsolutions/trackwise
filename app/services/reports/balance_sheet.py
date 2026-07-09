"""Balance Sheet report derived from journal entries."""

from models import db, ChartOfAccounts, JournalLine, JournalEntry


def get_balance_sheet(business_id, as_of_date=None):
    """Generate a Balance Sheet from journal entries.
    
    Args:
        business_id: The business to generate the report for
        as_of_date: Optional date to calculate balances as of (datetime)
    
    Returns:
        dict with assets, liabilities, equity, and verification
    """
    # Get all accounts for the business
    accounts = ChartOfAccounts.query.filter_by(
        business_id=business_id, is_active=True
    ).all()
    
    # Build account type mapping
    asset_accounts = [a for a in accounts if a.type == 'asset']
    liability_accounts = [a for a in accounts if a.type == 'liability']
    equity_accounts = [a for a in accounts if a.type == 'equity']
    
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
    
    # Calculate asset balances (debit balance for asset accounts)
    total_assets = 0.0
    assets = []
    for acct in asset_accounts:
        bal = account_balances.get(acct.id, {'debit': 0, 'credit': 0})
        # Asset accounts have debit balances
        balance = bal['debit'] - bal['credit']
        if balance != 0:
            assets.append({
                'account': acct,
                'balance': balance,
            })
            total_assets += balance
    
    # Calculate liability balances (credit balance for liability accounts)
    total_liabilities = 0.0
    liabilities = []
    for acct in liability_accounts:
        bal = account_balances.get(acct.id, {'debit': 0, 'credit': 0})
        # Liability accounts have credit balances
        balance = bal['credit'] - bal['debit']
        if balance != 0:
            liabilities.append({
                'account': acct,
                'balance': balance,
            })
            total_liabilities += balance
    
    # Calculate equity balances (credit balance for equity accounts)
    total_equity = 0.0
    equity = []
    for acct in equity_accounts:
        bal = account_balances.get(acct.id, {'debit': 0, 'credit': 0})
        # Equity accounts have credit balances
        balance = bal['credit'] - bal['debit']
        if balance != 0:
            equity.append({
                'account': acct,
                'balance': balance,
            })
            total_equity += balance
    
    # Verify accounting equation
    is_balanced = abs(total_assets - (total_liabilities + total_equity)) < 0.01
    
    return {
        'total_assets': total_assets,
        'assets': assets,
        'total_liabilities': total_liabilities,
        'liabilities': liabilities,
        'total_equity': total_equity,
        'equity': equity,
        'is_balanced': is_balanced,
        'difference': total_assets - (total_liabilities + total_equity),
        'as_of_date': as_of_date,
    }