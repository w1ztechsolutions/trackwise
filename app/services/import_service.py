"""Spreadsheet import handlers for bank statements, journal entries, and parties."""

import uuid
from datetime import datetime, time
from decimal import Decimal

from app.models import BankStatement, ChartOfAccounts, Customer, Supplier, db
from app.services.accounting_service import AccountingException, post_entry
from app.services.reconciliation_period_service import (
    ReconciliationPeriodClosedError,
    assert_reconciliation_open,
)
from app.services.xlsx_import import normalize_text, parse_date, parse_decimal


class ImportValidationError(ValueError):
    """Raised when import rows cannot be processed."""


BANK_STATEMENT_COLUMNS = {
    'date': ('date', 'statement_date', 'transaction_date', 'value date'),
    'amount': ('amount', 'value', 'debit', 'credit'),
    'description': ('description', 'details', 'narrative', 'particulars'),
    'reference': ('reference', 'ref', 'transaction reference', 'transaction id'),
}

JOURNAL_COLUMNS = {
    'date': ('date', 'entry_date', 'posting date'),
    'description': ('description', 'narrative', 'details'),
    'account_code': ('account_code', 'account code', 'code', 'account'),
    'debit': ('debit', 'debit_amount', 'dr'),
    'credit': ('credit', 'credit_amount', 'cr'),
}

PARTY_COLUMNS = {
    'name': ('name', 'supplier name', 'customer name', 'party name', 'company'),
    'email': ('email', 'email address', 'e-mail'),
    'phone': ('phone', 'telephone', 'mobile', 'contact number'),
    'address': ('address', 'location', 'street address'),
}


IGNORE_FIELD = '__ignore__'


def resolve_columns(rows, column_map=None, defaults=None):
    """Map logical field names to actual worksheet header keys.

    ``column_map`` provides explicit ``{field: header}`` choices made by the
    user. A field mapped to :data:`IGNORE_FIELD` is deliberately left unresolved
    and never auto-detected. Every other field falls back to case-insensitive
    header-name matching against the aliases in ``defaults``, so a partially
    filled mapping no longer discards alias knowledge.
    """
    if not rows:
        return {}

    available = list(rows[0].keys())
    lowered = {header.lower().strip(): header for header in available}
    explicit = column_map or {}
    defaults = defaults or {}

    def explicit_header(choice):
        candidates = [choice] if isinstance(choice, str) else list(choice or [])
        for candidate in candidates:
            if candidate is None or candidate == IGNORE_FIELD:
                continue
            header = lowered.get(str(candidate).strip().lower())
            if header is not None:
                return header
        return None

    resolved = {}
    fields = list(defaults) + [field for field in explicit if field not in defaults]
    for field in fields:
        if field in explicit:
            if explicit[field] == IGNORE_FIELD:
                continue
            header = explicit_header(explicit[field])
            if header is not None:
                resolved[field] = header
                continue
        for alias in defaults.get(field, ()):
            header = lowered.get(str(alias).strip().lower())
            if header is not None:
                resolved[field] = header
                break
    return resolved


def _row_value(row, resolved, field):
    header = resolved.get(field)
    if header is None:
        return None
    return row.get(header)


def _require_mapping(resolved, entity, required):
    missing = [field for field in required if field not in resolved]
    if missing:
        raise ImportValidationError(
            f'Map the {", ".join(missing)} column(s) before importing {entity}.'
        )


def import_bank_statements(business_id, account_id, rows, column_map=None, date_order='MDY'):
    """Import bank statement lines, skipping references already imported."""
    if business_id is None:
        raise ImportValidationError('business_id is required')

    account = db.session.get(ChartOfAccounts, account_id)
    if account is None or account.business_id != business_id:
        raise ImportValidationError('Select a valid bank account for this business.')

    # Check if any statement dates fall in a locked reconciliation period
    # We'll check each row's date individually during the loop
    resolved = resolve_columns(rows, column_map, BANK_STATEMENT_COLUMNS)
    _require_mapping(resolved, 'bank statements', ('date', 'amount'))

    existing_references = {
        row[0] for row in db.session.query(BankStatement.reference).filter(
            BankStatement.business_id == business_id,
            BankStatement.account_id == account_id,
            BankStatement.reference.isnot(None),
        ).all()
    }

    imported = 0
    duplicates = 0
    errors = []
    for index, row in enumerate(rows, start=2):
        statement_date = parse_date(_row_value(row, resolved, 'date'), date_order)
        amount = parse_decimal(_row_value(row, resolved, 'amount'))
        if statement_date is None or amount is None:
            errors.append(f'Row {index}: a valid date and amount are required.')
            continue

        # Check reconciliation period lock
        try:
            assert_reconciliation_open(business_id, account_id, datetime.combine(statement_date, time.min))
        except ReconciliationPeriodClosedError as e:
            errors.append(f'Row {index}: {e}')
            continue

        reference = normalize_text(_row_value(row, resolved, 'reference')) or None
        if reference and reference in existing_references:
            duplicates += 1
            continue

        db.session.add(BankStatement(
            business_id=business_id,
            account_id=account_id,
            statement_date=datetime.combine(statement_date, time.min),
            description=normalize_text(_row_value(row, resolved, 'description')) or 'Imported statement line',
            amount=amount,
            reference=reference,
        ))
        if reference:
            existing_references.add(reference)
        imported += 1

    return {'imported': imported, 'duplicates': duplicates, 'errors': errors}


def import_journal_entries(business_id, rows, column_map=None, created_by=None, date_order='MDY'):
    """Import journal entries, grouping consecutive lines by date and description."""
    if business_id is None:
        raise ImportValidationError('business_id is required')

    resolved = resolve_columns(rows, column_map, JOURNAL_COLUMNS)
    _require_mapping(
        resolved, 'journal entries', ('date', 'description', 'account_code'),
    )

    accounts = {
        account.code: account
        for account in ChartOfAccounts.query.filter(
            ChartOfAccounts.business_id == business_id,
            ChartOfAccounts.is_active.is_(True),
        ).all()
    }

    entries = []
    current_key = None
    current_lines = []
    imported = 0
    errors = []

    def flush():
        nonlocal imported
        if len(current_lines) < 2:
            errors.append(
                f'{current_key[1]}: needs at least two debit/credit lines to post a '
                f'journal entry (received {len(current_lines)}).'
            )
            return
        total_debit = sum(line['debit_amount'] for line in current_lines)
        total_credit = sum(line['credit_amount'] for line in current_lines)
        if abs(total_debit - total_credit) > Decimal('0.01'):
            errors.append(
                f'{current_key[1]} does not balance: debits={total_debit}, credits={total_credit}.'
            )
            return
        try:
            post_entry(
                business_id,
                datetime.combine(current_key[0], time.min),
                current_key[1],
                current_lines,
                reference_type='JournalEntry',
                created_by=created_by,
                commit=False,
            )
        except AccountingException as error:
            errors.append(f'{current_key[1]}: {error}')
            return
        entries.append(current_key[1])
        imported += 1

    for index, row in enumerate(rows, start=2):
        entry_date = parse_date(_row_value(row, resolved, 'date'), date_order)
        code = normalize_text(_row_value(row, resolved, 'account_code'))
        debit = parse_decimal(_row_value(row, resolved, 'debit')) or Decimal('0')
        credit = parse_decimal(_row_value(row, resolved, 'credit')) or Decimal('0')
        if debit < 0:
            debit, credit = -debit, credit
        if credit < 0:
            debit, credit = debit, -credit

        if entry_date is None or not code:
            errors.append(f'Row {index}: a valid date and account code are required.')
            continue
        if debit > 0 and credit > 0:
            errors.append(f'Row {index}: a line cannot be both a debit and a credit.')
            continue
        if debit == 0 and credit == 0:
            continue

        account = accounts.get(code)
        if account is None:
            errors.append(f'Row {index}: account {code} was not found for this business.')
            continue

        key = (entry_date, normalize_text(_row_value(row, resolved, 'description')) or 'Imported journal entry')
        if current_key is not None and key != current_key:
            flush()
            current_lines = []
        current_key = key
        current_lines.append({
            'account_id': account.id,
            'debit_amount': float(debit),
            'credit_amount': float(credit),
        })

    if current_key is not None:
        flush()

    return {'imported': imported, 'duplicates': 0, 'errors': errors}


def import_suppliers(business_id, rows, column_map=None):
    """Import suppliers, skipping duplicate name and email combinations."""
    resolved = resolve_columns(rows, column_map, PARTY_COLUMNS)
    _require_mapping(resolved, 'supplier records', ('name',))

    existing = {
        (row[0].lower(), (row[1] or '').lower())
        for row in db.session.query(Supplier.name, Supplier.email).filter(
            Supplier.business_id == business_id,
        ).all()
    }

    imported = 0
    duplicates = 0
    errors = []
    for index, row in enumerate(rows, start=2):
        name = normalize_text(_row_value(row, resolved, 'name'))
        if not name:
            errors.append(f'Row {index}: a supplier name is required.')
            continue

        email = normalize_text(_row_value(row, resolved, 'email')) or None
        key = (name.lower(), (email or '').lower())
        if key in existing:
            duplicates += 1
            continue

        db.session.add(Supplier(
            business_id=business_id,
            supplier_id=f'SUPP-{uuid.uuid4().hex[:8].upper()}',
            name=name,
            email=email,
            phone=normalize_text(_row_value(row, resolved, 'phone')) or None,
            address=normalize_text(_row_value(row, resolved, 'address')) or None,
            is_active=True,
        ))
        existing.add(key)
        imported += 1

    return {'imported': imported, 'duplicates': duplicates, 'errors': errors}


def import_customers(business_id, rows, column_map=None):
    """Import customers, skipping duplicate name and email combinations."""
    resolved = resolve_columns(rows, column_map, PARTY_COLUMNS)
    _require_mapping(resolved, 'customer records', ('name',))

    existing = {
        (row[0].lower(), (row[1] or '').lower())
        for row in db.session.query(Customer.name, Customer.email).filter(
            Customer.business_id == business_id,
        ).all()
    }

    imported = 0
    duplicates = 0
    errors = []
    for index, row in enumerate(rows, start=2):
        name = normalize_text(_row_value(row, resolved, 'name'))
        if not name:
            errors.append(f'Row {index}: a customer name is required.')
            continue

        email = normalize_text(_row_value(row, resolved, 'email')) or None
        key = (name.lower(), (email or '').lower())
        if key in existing:
            duplicates += 1
            continue

        db.session.add(Customer(
            business_id=business_id,
            customer_id=f'CUST-{uuid.uuid4().hex[:8].upper()}',
            name=name,
            email=email,
            phone=normalize_text(_row_value(row, resolved, 'phone')) or None,
            address=normalize_text(_row_value(row, resolved, 'address')) or None,
            is_active=True,
        ))
        existing.add(key)
        imported += 1

    return {'imported': imported, 'duplicates': duplicates, 'errors': errors}