"""Cash Flow Statement report derived from journal entries."""

from datetime import datetime
from models import db, ChartOfAccounts, JournalLine, JournalEntry, Invoice, Bill


def get_cash_flow(business_id, start_date=None, end_date=None):
    """Generate a Cash Flow Statement from journal entries.
    
    Args:
        business_id: The business to generate the report for
        start_date: Optional start date filter (datetime)
        end_date: Optional end date filter (datetime)
    
    Returns:
        dict with operating, investing, financing activities
    """
    # Get all accounts for the business
    accounts = ChartOfAccounts.query.filter_by(
        business_id=business_id, is_active=True
    ).all()
    
    # Build account code mapping
    cash_acct = next((a for a in accounts if a.code == '1000'), None)
    ar_acct = next((a for a in accounts if a.code == '1200'), None)
    inventory_acct = next((a for a in accounts if a.code == '1400'), None)
    ap_acct = next((a for a in accounts if a.code == '2100'), None)
    revenue_acct = next((a for a in accounts if a.code == '4000'), None)
    cogs_acct = next((a for a in accounts if a.code == '5000'), None)
    
    # Query journal lines with date filtering
    line_query = db.session.query(
        JournalLine.account_id,
        db.func.sum(JournalLine.debit_amount).label('total_debit'),
        db.func.sum(JournalLine.credit_amount).label('total_credit'),
    ).join(JournalEntry).filter(
        JournalEntry.business_id == business_id
    )
    
    if start_date:
        line_query = line_query.filter(JournalEntry.entry_date >= start_date)
    if end_date:
        line_query = line_query.filter(JournalEntry.entry_date <= end_date)
    
    line_query = line_query.group_by(JournalLine.account_id)
    
    # Get account balances
    account_balances = {}
    for row in line_query.all():
        account_balances[row.account_id] = {
            'debit': float(row.total_debit or 0),
            'credit': float(row.total_credit or 0),
        }
    
    # Operating activities
    # Net income from income statement
    operating = {
        'net_income': 0.0,
        'adjustments': [],
        'total': 0.0,
    }
    
    # Calculate net income (simplified - from revenue and expenses)
    if revenue_acct:
        rev_bal = account_balances.get(revenue_acct.id, {'debit': 0, 'credit': 0})
        operating['net_income'] = rev_bal['credit'] - rev_bal['debit']
    
    if cogs_acct:
        cogs_bal = account_balances.get(cogs_acct.id, {'debit': 0, 'credit': 0})
        operating['net_income'] -= cogs_bal['debit'] - cogs_bal['credit']
    
    # Add expense adjustments
    expense_accounts = [a for a in accounts if a.type == 'expense' and a.code != '5000']
    for acct in expense_accounts:
        bal = account_balances.get(acct.id, {'debit': 0, 'credit': 0})
        expense = bal['debit'] - bal['credit']
        if expense > 0:
            operating['adjustments'].append({
                'name': acct.name,
                'amount': expense,
            })
            operating['net_income'] -= expense
    
    operating['total'] = operating['net_income']
    
    # Investing activities - track fixed asset purchases
    investing = {
        'items': [],
        'total': 0.0,
    }
    
    # Look for fixed asset account (1500) transactions
    fixed_asset_acct = next((a for a in accounts if a.code == '1500'), None)
    if fixed_asset_acct:
        fa_bal = account_balances.get(fixed_asset_acct.id, {'debit': 0, 'credit': 0})
        if fa_bal['debit'] > 0:
            investing['items'].append({
                'name': 'Fixed Asset Purchases',
                'amount': fa_bal['debit'],
            })
            investing['total'] -= fa_bal['debit']  # Cash outflow
    
    # Financing activities - track capital/loan transactions
    financing = {
        'items': [],
        'total': 0.0,
    }
    
    # Look for capital account (3000) transactions
    capital_acct = next((a for a in accounts if a.code == '3000'), None)
    if capital_acct:
        cap_bal = account_balances.get(capital_acct.id, {'debit': 0, 'credit': 0})
        if cap_bal['credit'] > 0:
            financing['items'].append({
                'name': 'Capital Contributions',
                'amount': cap_bal['credit'],
            })
            financing['total'] += cap_bal['credit']
        if cap_bal['debit'] > 0:
            financing['items'].append({
                'name': 'Capital Withdrawals',
                'amount': -cap_bal['debit'],
            })
            financing['total'] -= cap_bal['debit']
    
    # Calculate net cash flow
    net_cash = operating['total'] + investing['total'] + financing['total']
    
    return {
        'operating': operating,
        'investing': investing,
        'financing': financing,
        'net_cash': net_cash,
        'start_date': start_date,
        'end_date': end_date,
    }