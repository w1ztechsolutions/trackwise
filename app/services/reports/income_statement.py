"""Income Statement report derived from journal entries."""

from datetime import datetime
from models import db, ChartOfAccounts, JournalLine, JournalEntry


def get_income_statement(business_id, start_date=None, end_date=None):
    """Generate an Income Statement from journal entries.
    
    Args:
        business_id: The business to generate the report for
        start_date: Optional start date filter (datetime)
        end_date: Optional end date filter (datetime)
    
    Returns:
        dict with revenue, cogs, expenses, and calculated profit figures
    """
    # Get all accounts for the business
    accounts = ChartOfAccounts.query.filter_by(
        business_id=business_id, is_active=True
    ).all()
    
    # Build account type mapping
    income_accounts = [a for a in accounts if a.type == 'income']
    cogs_accounts = [a for a in accounts if a.type == 'expense' and a.code == '5000']
    expense_accounts = [a for a in accounts if a.type == 'expense' and a.code != '5000']
    
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
    
    # Calculate revenue (credit balance for income accounts)
    total_revenue = 0.0
    revenue_by_account = {}
    for acct in income_accounts:
        bal = account_balances.get(acct.id, {'debit': 0, 'credit': 0})
        # Income accounts have credit balances (revenue increases on credit)
        revenue = bal['credit'] - bal['debit']
        if revenue > 0:
            revenue_by_account[acct.name] = revenue
            total_revenue += revenue
    
    # Calculate COGS (debit balance for COGS accounts)
    total_cogs = 0.0
    cogs_by_account = {}
    for acct in cogs_accounts:
        bal = account_balances.get(acct.id, {'debit': 0, 'credit': 0})
        # COGS accounts have debit balances
        cogs = bal['debit'] - bal['credit']
        if cogs > 0:
            cogs_by_account[acct.name] = cogs
            total_cogs += cogs
    
    # Calculate operating expenses (debit balance for expense accounts)
    total_expenses = 0.0
    expenses_by_category = {}
    for acct in expense_accounts:
        bal = account_balances.get(acct.id, {'debit': 0, 'credit': 0})
        # Expense accounts have debit balances
        expense = bal['debit'] - bal['credit']
        if expense > 0:
            expenses_by_category[acct.name] = expense
            total_expenses += expense
    
    # Calculate profit figures
    gross_profit = total_revenue - total_cogs
    pre_tax_profit = gross_profit - total_expenses
    
    # Get tax rate from settings
    from models import Setting
    tax_setting = Setting.query.filter_by(key='tax_rate').first()
    tax_rate = float(tax_setting.value) if tax_setting else 30.0
    tax_amount = max(0.0, pre_tax_profit * (tax_rate / 100.0))
    net_profit = pre_tax_profit - tax_amount
    
    return {
        'total_revenue': total_revenue,
        'revenue_by_account': revenue_by_account,
        'total_cogs': total_cogs,
        'cogs_by_account': cogs_by_account,
        'gross_profit': gross_profit,
        'total_expenses': total_expenses,
        'expenses_by_category': expenses_by_category,
        'pre_tax_profit': pre_tax_profit,
        'tax_rate': tax_rate,
        'tax_amount': tax_amount,
        'net_profit': net_profit,
        'start_date': start_date,
        'end_date': end_date,
    }