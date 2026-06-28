import json
from datetime import datetime

from models import db, ChartOfAccounts, JournalEntry, JournalLine, AuditLog, User


class AccountingException(Exception):
    pass


def post_entry(business_id, entry_date, description, lines, reference_type=None, reference_id=None, created_by=None):
    if business_id is None:
        raise AccountingException("business_id is required")
    if not lines:
        raise AccountingException("Journal entry must have at least one line")

    total_debit = float(sum(l.get('debit_amount', 0) or 0 for l in lines))
    total_credit = float(sum(l.get('credit_amount', 0) or 0 for l in lines))

    if abs(total_debit - total_credit) > 0.01:
        raise AccountingException(
            f"Entry does not balance: debits={total_debit}, credits={total_credit}"
        )

    account_ids = [l['account_id'] for l in lines]
    accounts = ChartOfAccounts.query.filter(
        ChartOfAccounts.id.in_(account_ids),
        ChartOfAccounts.business_id == business_id,
        ChartOfAccounts.is_active == True,
    ).all()
    found_ids = {a.id for a in accounts}
    missing = set(account_ids) - found_ids
    if missing:
        raise AccountingException(f"Account(s) not found or inactive: {missing}")

    entry = JournalEntry(
        business_id=business_id,
        entry_date=entry_date or datetime.utcnow(),
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
        created_by=created_by,
    )
    db.session.add(entry)
    db.session.flush()

    for line_data in lines:
        line = JournalLine(
            journal_entry_id=entry.id,
            account_id=line_data['account_id'],
            debit_amount=float(line_data.get('debit_amount', 0) or 0),
            credit_amount=float(line_data.get('credit_amount', 0) or 0),
        )
        db.session.add(line)

    db.session.commit()
    _log_audit(
        business_id, created_by, 'CREATE', 'journal_entries', entry.id,
        None,
        {
            'entry_date': str(entry.entry_date),
            'description': description,
            'lines': [
                {'account_id': l['account_id'], 'debit_amount': l.get('debit_amount', 0), 'credit_amount': l.get('credit_amount', 0)}
                for l in lines
            ],
        },
    )
    db.session.commit()
    return entry


def _log_audit(business_id, user_id, action, table_name, record_id, old_values=None, new_values=None):
    log = AuditLog(
        business_id=business_id,
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_values=json.dumps(old_values, default=str) if old_values else None,
        new_values=json.dumps(new_values, default=str) if new_values else None,
    )
    db.session.add(log)


def get_ledger_balances(business_id, account_ids=None):
    line_sums = db.session.query(
        JournalLine.account_id,
        db.func.sum(JournalLine.debit_amount).label('total_debit'),
        db.func.sum(JournalLine.credit_amount).label('total_credit'),
    ).join(JournalEntry).filter(JournalEntry.business_id == business_id)

    if account_ids:
        line_sums = line_sums.filter(JournalLine.account_id.in_(account_ids))

    line_sums = line_sums.group_by(JournalLine.account_id).subquery()

    results = db.session.query(
        ChartOfAccounts,
        line_sums.c.total_debit,
        line_sums.c.total_credit,
    ).outerjoin(
        line_sums, ChartOfAccounts.id == line_sums.c.account_id
    ).filter(ChartOfAccounts.business_id == business_id).all()

    balances = []
    for account, total_debit, total_credit in results:
        debit = float(total_debit or 0.0)
        credit = float(total_credit or 0.0)
        balance = debit - credit
        balances.append({
            'account': account,
            'debit': debit,
            'credit': credit,
            'balance': balance,
        })

    return balances


def get_account_by_code(business_id, code):
    return ChartOfAccounts.query.filter_by(
        business_id=business_id, code=code, is_active=True
    ).first()


def verify_balances(business_id):
    line_sums = db.session.query(
        JournalLine.journal_entry_id,
        db.func.sum(JournalLine.debit_amount).label('total_debit'),
        db.func.sum(JournalLine.credit_amount).label('total_credit'),
    ).join(JournalEntry).filter(JournalEntry.business_id == business_id)
    line_sums = line_sums.group_by(JournalLine.journal_entry_id).subquery()

    results = db.session.query(
        JournalEntry,
        line_sums.c.total_debit,
        line_sums.c.total_credit,
    ).outerjoin(
        line_sums, JournalEntry.id == line_sums.c.journal_entry_id
    ).filter(JournalEntry.business_id == business_id).all()

    balanced = []
    unbalanced = []
    for entry, total_debit, total_credit in results:
        d = float(total_debit or 0.0)
        c = float(total_credit or 0.0)
        if abs(d - c) > 0.01:
            unbalanced.append({
                'entry_id': entry.id,
                'description': entry.description,
                'debits': d,
                'credits': c,
                'difference': d - c,
            })
        else:
            balanced.append({
                'entry_id': entry.id,
                'description': entry.description,
                'amount': d,
            })

    return {
        'business_id': business_id,
        'balanced_count': len(balanced),
        'unbalanced_count': len(unbalanced),
        'unbalanced': unbalanced,
        'balanced': balanced,
    }
