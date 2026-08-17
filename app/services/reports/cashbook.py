"""Cashbook report derived from journal entries.

The cashbook combines the Cash (account 1000) and Bank (account 1100)
accounts into a single, time-ordered register with running balances,
summary totals, and date-range filtering. It follows the same read-only,
double-entry-derived pattern used by all TrackWise reports.
"""

from app.models import db, ChartOfAccounts, JournalLine, JournalEntry, User


CASHBOOK_ACCOUNT_CODES = ('1000', '1100')


def get_cashbook(business_id, start_date=None, end_date=None):
    """Generate a Cashbook report from journal entries.

    Combines the Cash (``1000``) and Bank (``1100``) asset accounts into a
    single chronological register with running balances and summary totals.

    Args:
        business_id: The business to generate the report for.
        start_date: Optional start date filter (datetime).
        end_date: Optional end date filter (datetime).

    Returns:
        dict with ``entries``, ``accounts``, ``total_debits``,
        ``total_credits``, ``net_cash_flow``, ``opening_balance``,
        ``closing_balance``, ``start_date`` and ``end_date``.
    """
    # 1. Resolve Cash and Bank ChartOfAccounts records
    accounts = (
        ChartOfAccounts.query
        .filter(
            ChartOfAccounts.business_id == business_id,
            ChartOfAccounts.code.in_(CASHBOOK_ACCOUNT_CODES),
            ChartOfAccounts.is_active == True,
        )
        .order_by(ChartOfAccounts.code)
        .all()
    )

    account_ids = [a.id for a in accounts]

    # 2. Compute opening balance — net of all cash/bank lines *before* the
    #    start date.  When no start_date is supplied there is no "before"
    #    period, so the opening balance is zero.
    opening_balance = 0.0
    if account_ids and start_date:
        opening_query = (
            db.session.query(
                db.func.coalesce(db.func.sum(JournalLine.debit_amount), 0),
                db.func.coalesce(db.func.sum(JournalLine.credit_amount), 0),
            )
            .join(JournalEntry)
            .filter(
                JournalEntry.business_id == business_id,
                JournalLine.account_id.in_(account_ids),
                JournalEntry.entry_date < start_date,
            )
        )
        o_debit, o_credit = opening_query.one()
        opening_balance = float(o_debit or 0) - float(o_credit or 0)

    # 3. Query journal lines within the (optional) date range, ordered
    #    chronologically.
    entries = []
    running_balance = opening_balance
    total_debits = 0.0
    total_credits = 0.0

    if account_ids:
        line_query = (
            db.session.query(JournalLine, JournalEntry, ChartOfAccounts)
            .join(JournalEntry)
            .join(ChartOfAccounts, JournalLine.account_id == ChartOfAccounts.id)
            .filter(
                JournalEntry.business_id == business_id,
                JournalLine.account_id.in_(account_ids),
            )
        )

        if start_date:
            line_query = line_query.filter(JournalEntry.entry_date >= start_date)
        if end_date:
            line_query = line_query.filter(JournalEntry.entry_date <= end_date)

        line_query = line_query.order_by(
            JournalEntry.entry_date.asc(),
            JournalEntry.id.asc(),
            JournalLine.id.asc(),
        )

        for line, entry, acct in line_query.all():
            debit = float(line.debit_amount or 0)
            credit = float(line.credit_amount or 0)

            # Asset convention: receipts (Dr) increase, payments (Cr) decrease
            running_balance += debit - credit
            total_debits += debit
            total_credits += credit

            entries.append({
                'date': entry.entry_date,
                'entry_id': entry.id,
                'description': entry.description,
                'reference_type': entry.reference_type,
                'reference_id': entry.reference_id,
                'account_code': acct.code,
                'account_name': acct.name,
                'debit': debit,
                'credit': credit,
                'balance': running_balance,
                'created_by': entry.created_by,
                'created_at': entry.created_at,
            })

    # 9. Resolve created_by user IDs to display names (avoids N+1 queries)
    user_ids = {e['created_by'] for e in entries if e.get('created_by') is not None}
    users = {}
    if user_ids:
        for u in (
            db.session.query(User.id, User.name, User.email)
            .filter(User.id.in_(user_ids))
            .all()
        ):
            display = u.name or u.email or str(u.id)
            users[u.id] = display

    for e in entries:
        e['created_by_name'] = users.get(e.get('created_by'), 'Unknown')

    net_cash_flow = total_debits - total_credits
    closing_balance = opening_balance + net_cash_flow

    return {
        'entries': entries,
        'accounts': accounts,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'net_cash_flow': net_cash_flow,
        'opening_balance': opening_balance,
        'closing_balance': closing_balance,
        'start_date': start_date,
        'end_date': end_date,
    }
