"""VAT return report: input and output tax per period, derived from the
VAT Payable control account (2200).

Output VAT posts as credits on sales; recoverable input VAT posts as
debits on purchases. The period balance (credits minus debits) is the
net VAT payable to MRA — or reclaimable when negative.
"""

from datetime import date, datetime
from decimal import Decimal

from app.models import ChartOfAccounts, JournalEntry, JournalLine, db

VAT_ACCOUNT_CODE = '2200'


def _month_bounds(today=None):
    """Return (start, end) datetimes covering the given day's month."""
    today = today or date.today()
    start = datetime(today.year, today.month, 1)
    if today.month == 12:
        end = datetime(today.year + 1, 1, 1)
    else:
        end = datetime(today.year, today.month + 1, 1)
    return start, end


def get_vat_return(business_id, start_date=None, end_date=None):
    """Generate the VAT return for a period.

    Args:
        business_id: tenant scope.
        start_date / end_date: datetimes bounding the period. When both are
            omitted the current calendar month is used.

    Returns:
        dict with output_tax, input_tax, net_vat, payable flag, and the
        contributing journal lines for audit trail. When the business has
        no VAT control account the report is empty but well-formed.
    """
    if start_date is None and end_date is None:
        start_date, end_date = _month_bounds()

    vat_account = ChartOfAccounts.query.filter_by(
        business_id=business_id,
        code=VAT_ACCOUNT_CODE,
        is_active=True,
    ).first()

    result = {
        'vat_account': vat_account,
        'start_date': start_date,
        'end_date': end_date,
        'output_tax': Decimal('0.00'),
        'input_tax': Decimal('0.00'),
        'net_vat': Decimal('0.00'),
        'is_payable': True,
        'lines': [],
    }
    if vat_account is None:
        return result

    query = (
        JournalLine.query.join(JournalEntry)
        .filter(
            JournalLine.account_id == vat_account.id,
            JournalEntry.business_id == business_id,
            JournalEntry.is_deleted.is_(False),
        )
    )
    if start_date is not None:
        query = query.filter(JournalEntry.entry_date >= start_date)
    if end_date is not None:
        query = query.filter(JournalEntry.entry_date < end_date)
    query = query.order_by(JournalEntry.entry_date.asc(), JournalEntry.id.asc())

    lines = []
    output_tax = Decimal('0.00')
    input_tax = Decimal('0.00')

    for line in query.all():
        entry = line.journal_entry
        debit = Decimal(line.debit_amount or 0)
        credit = Decimal(line.credit_amount or 0)
        if debit == 0 and credit == 0:
            continue
        input_tax += debit
        output_tax += credit
        lines.append({
            'entry_date': entry.entry_date,
            'reference_type': entry.reference_type,
            'description': entry.description,
            'debit': debit,
            'credit': credit,
        })

    net_vat = output_tax - input_tax
    result.update({
        'output_tax': output_tax,
        'input_tax': input_tax,
        'net_vat': net_vat,
        'is_payable': net_vat >= 0,
        'lines': lines,
    })
    return result
