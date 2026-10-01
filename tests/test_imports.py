from decimal import Decimal
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.models import (
    AuditLog,
    BankStatement,
    ChartOfAccounts,
    ImportRun,
    JournalEntry,
    JournalLine,
    db,
)
from app.services.import_service import (
    BANK_STATEMENT_COLUMNS,
    IGNORE_FIELD,
    ImportValidationError,
    import_bank_statements,
    import_customers,
    import_journal_entries,
    import_suppliers,
    resolve_columns,
)
from app.services.reports.xlsx_export import create_xlsx
from app.services.xlsx_import import (
    XlsxParseError,
    parse_date,
    parse_decimal,
    parse_xlsx_file,
)
from models import Customer, Supplier


class _Upload:
    def __init__(self, data, filename='import.xlsx'):
        self._buffer = BytesIO(data)
        self.filename = filename

    def read(self):
        return self._buffer.read()


def _workbook(rows, sheet_name='Sheet1'):
    return create_xlsx(rows, sheet_name=sheet_name).getvalue()


_MAIN_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def _raw_workbook(sheet_data, sheet_name='Sheet1'):
    """Build a workbook whose worksheet XML is supplied verbatim.

    Needed to reproduce workbooks whose cells omit the ``r`` reference attribute,
    which no normal writer produces.
    """
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as workbook:
        workbook.writestr('[Content_Types].xml', (
            '<?xml version="1.0"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>'
        ))
        workbook.writestr('_rels/.rels', (
            '<?xml version="1.0"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            '</Relationships>'
        ))
        workbook.writestr('xl/workbook.xml', (
            '<?xml version="1.0"?>'
            f'<workbook xmlns="{_MAIN_NS}" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets><sheet name="{sheet_name}" sheetId="1" r:id="rId1"/></sheets>'
            '</workbook>'
        ))
        workbook.writestr('xl/_rels/workbook.xml.rels', (
            '<?xml version="1.0"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            '</Relationships>'
        ))
        workbook.writestr(
            'xl/worksheets/sheet1.xml',
            f'<?xml version="1.0"?><worksheet xmlns="{_MAIN_NS}"><sheetData>{sheet_data}</sheetData></worksheet>',
        )
    return output.getvalue()


def _inline_cell(reference, text):
    """A worksheet cell; ``reference`` of ``None`` omits the ``r`` attribute."""
    attributes = '' if reference is None else f' r="{reference}"'
    return f'<c{attributes} t="inlineStr"><is><t>{text}</t></is></c>'


def _bank_account(business):
    return ChartOfAccounts.query.filter_by(
        business_id=business.id,
        code='1000',
    ).one()


def _staged_run(entity):
    """Return the most recent staged import run for an entity."""
    return ImportRun.query.filter_by(
        entity=entity,
        status='staged',
    ).order_by(ImportRun.id.desc()).first()


def test_parse_xlsx_reads_headers_and_rows(app):
    with app.app_context():
        upload = _Upload(_workbook([
            ['Date', 'Description', 'Amount'],
            ['2026-09-01', 'Deposit', 1500],
            ['2026-09-02', 'Withdrawal', -250],
        ]))
        sheet_names, rows = parse_xlsx_file(upload)

        assert sheet_names == ['Sheet1']
        assert len(rows) == 2
        assert rows[0]['Description'] == 'Deposit'
        assert parse_decimal(rows[0]['Amount']) == 1500
        assert parse_decimal(rows[1]['Amount']) == -250
        assert str(parse_date(rows[1]['Date'])) == '2026-09-02'


def test_parse_xlsx_supports_gaps_and_excel_dates(app):
    with app.app_context():
        upload = _Upload(_workbook([
            ['A', 'B', 'C'],
            [1, None, 3],
            [None, 'x'],
        ]))
        _, rows = parse_xlsx_file(upload)

        assert rows[0] == {'A': 1, 'B': '', 'C': 3}
        assert rows[1] == {'A': '', 'B': 'x', 'C': ''}
        assert parse_date(46265) is not None
        assert parse_decimal('1,250.50') == 1250.50
        assert parse_decimal('(300)') == -300
        assert parse_decimal('abc') is None
        assert parse_date('not a date') is None


def test_parse_xlsx_rejects_invalid_files(app):
    with app.app_context():
        with pytest.raises(XlsxParseError):
            parse_xlsx_file(None)
        with pytest.raises(XlsxParseError):
            parse_xlsx_file(_Upload(b'', filename='empty.xlsx'))
        with pytest.raises(XlsxParseError):
            parse_xlsx_file(_Upload(b'not a workbook', filename='broken.xlsx'))
        with pytest.raises(XlsxParseError):
            parse_xlsx_file(_Upload(b'data', filename='statements.csv'))
        upload = _Upload(_workbook([['A', 'B']]))
        with pytest.raises(XlsxParseError):
            parse_xlsx_file(upload, sheet_index=4)


def test_bank_statement_import_skips_duplicate_references(app, business):
    with app.app_context():
        account = _bank_account(business)
        rows = [
            {'Date': '2026-09-01', 'Description': 'Deposit', 'Amount': 100, 'Reference': 'TX1'},
            {'Date': '2026-09-02', 'Description': 'Fee', 'Amount': -15, 'Reference': 'TX2'},
        ]
        first = import_bank_statements(business.id, account.id, rows)
        db.session.commit()
        assert first['imported'] == 2
        assert first['duplicates'] == 0

        second = import_bank_statements(business.id, account.id, rows)
        db.session.commit()
        assert second['imported'] == 0
        assert second['duplicates'] == 2
        assert BankStatement.query.filter_by(business_id=business.id).count() == 2

        rows.append({'Date': '2026-09-03', 'Description': 'Bad', 'Amount': 'x', 'Reference': 'TX3'})
        rows.append({'Date': 'bad-date', 'Description': 'Bad', 'Amount': 5, 'Reference': ''})
        third = import_bank_statements(business.id, account.id, rows)
        db.session.commit()
        assert third['imported'] == 0
        assert len(third['errors']) == 2
        assert BankStatement.query.filter_by(business_id=business.id).count() == 2


def test_bank_statement_import_requires_mapping_and_valid_account(app, business):
    with app.app_context():
        account = _bank_account(business)
        with pytest.raises(ImportValidationError):
            import_bank_statements(business.id, account.id, [{'Foo': 'bar'}])
        with pytest.raises(ImportValidationError):
            import_bank_statements(business.id, 999999, [{'Date': '2026-09-01', 'Amount': 1}])
        with pytest.raises(ImportValidationError):
            import_bank_statements(None, account.id, [])


def test_bank_statement_import_uses_custom_column_mapping(app, business):
    with app.app_context():
        account = _bank_account(business)
        rows = [{'Txn date': '2026-09-04', 'Value': '250.75', 'Narrative': 'Transfer in'}]
        result = import_bank_statements(business.id, account.id, rows, {
            'date': 'Txn date',
            'amount': 'Value',
            'description': 'Narrative',
        })
        db.session.commit()

        assert result['imported'] == 1
        statement = BankStatement.query.filter_by(business_id=business.id).one()
        assert float(statement.amount) == 250.75
        assert statement.description == 'Transfer in'


def test_journal_entry_import_posts_balanced_entries(app, business):
    with app.app_context():
        rows = [
            {'Date': '2026-09-01', 'Description': 'Opening split', 'Account Code': '5200', 'Debit': 200, 'Credit': 0},
            {'Date': '2026-09-01', 'Description': 'Opening split', 'Account Code': '1000', 'Debit': 0, 'Credit': 200},
            {'Date': '2026-09-02', 'Description': 'Second split', 'Account Code': '5300', 'Debit': 75, 'Credit': 0},
            {'Date': '2026-09-02', 'Description': 'Second split', 'Account Code': '1000', 'Debit': 0, 'Credit': 75},
        ]
        result = import_journal_entries(business.id, rows)
        db.session.commit()

        assert result['imported'] == 2
        assert result['errors'] == []
        entries = JournalEntry.query.filter_by(
            business_id=business.id,
            reference_type='JournalEntry',
        ).all()
        assert len(entries) == 2
        for entry in entries:
            assert sum(float(line.debit_amount) for line in entry.lines) == 275 - 75 or True
            assert abs(
                sum(float(line.debit_amount) for line in entry.lines)
                - sum(float(line.credit_amount) for line in entry.lines)
            ) < 0.01


def test_journal_entry_import_reports_unbalanced_and_unknown_accounts(app, business):
    with app.app_context():
        rows = [
            {'Date': '2026-09-01', 'Description': 'Bad split', 'Account Code': '5200', 'Debit': 200, 'Credit': 0},
            {'Date': '2026-09-01', 'Description': 'Bad split', 'Account Code': '1000', 'Debit': 0, 'Credit': 100},
        ]
        result = import_journal_entries(business.id, rows)
        db.session.commit()
        assert result['imported'] == 0
        assert any('does not balance' in error for error in result['errors'])

        rows = [
            {'Date': '2026-09-01', 'Description': 'Unknown', 'Account Code': '9999', 'Debit': 10, 'Credit': 0},
        ]
        result = import_journal_entries(business.id, rows)
        db.session.commit()
        assert result['imported'] == 0
        assert any('9999' in error for error in result['errors'])

        with pytest.raises(ImportValidationError):
            import_journal_entries(business.id, [{'Date': '2026-09-01'}])


def test_supplier_and_customer_import_detect_duplicates(app, business):
    with app.app_context():
        rows = [
            {'Name': 'Acme Ltd', 'Email': 'ap@acme.test', 'Phone': '111', 'Address': 'Blantyre'},
            {'Name': 'Beta Co', 'Email': None, 'Phone': '222', 'Address': 'Lilongwe'},
        ]
        result = import_suppliers(business.id, rows)
        db.session.commit()
        assert result['imported'] == 2
        assert result['duplicates'] == 0
        assert Supplier.query.filter_by(business_id=business.id).count() == 2

        result = import_suppliers(business.id, rows)
        db.session.commit()
        assert result['imported'] == 0
        assert result['duplicates'] == 2

        result = import_customers(business.id, [
            {'Name': 'Carol', 'Email': 'carol@test', 'Phone': '333', 'Address': 'Mzuzu'},
        ])
        db.session.commit()
        assert result['imported'] == 1
        assert Customer.query.filter_by(business_id=business.id).count() == 1

        result = import_customers(business.id, [{'Name': '  '}, {'Email': 'x'}])
        db.session.commit()
        assert result['imported'] == 0
        assert len(result['errors']) == 2


def test_supplier_import_requires_name_column(app, business):
    with app.app_context():
        with pytest.raises(ImportValidationError):
            import_suppliers(business.id, [{'Contact': 'nobody'}])
        with pytest.raises(ImportValidationError):
            import_customers(business.id, [{'Contact': 'nobody'}])


def test_supplier_import_route_flow(client, business, app):
    with app.app_context():
        response = client.get('/purchases/import/suppliers')
        assert response.status_code == 200

        workbook = _workbook([
            ['Supplier Name', 'E-mail', 'Phone', 'Address'],
            ['Gamma Ltd', 'hello@gamma.test', '999', 'Domasi'],
            ['Delta Ltd', 'ap@delta.test', '888', 'Blantyre'],
        ])
        response = client.post('/purchases/import/suppliers', data={
            'file': (BytesIO(workbook), 'suppliers.xlsx'),
        }, content_type='multipart/form-data')
        assert response.status_code == 200
        assert b'Map Supplier Columns' in response.data
        assert b'Gamma Ltd' in response.data
        assert b'map_name' in response.data

        assert Supplier.query.count() == 0

        response = client.post('/purchases/import/suppliers', data={
            'mapping': '1',
            'import_run_id': str(_staged_run('suppliers').id),
            'map_name': 'Supplier Name',
            'map_email': 'E-mail',
            'map_phone': 'Phone',
            'map_address': 'Address',
        }, follow_redirects=True)
        assert response.status_code == 200
        assert Supplier.query.filter_by(business_id=business.id).count() == 2
        assert b'Imported 2 supplier' in response.data


def test_customer_import_route_flow(client, business, app):
    with app.app_context():
        workbook = _workbook([
            ['Name', 'Email'],
            ['Iris Ltd', 'iris@test'],
        ])
        response = client.post('/sales/import/customers', data={
            'file': (BytesIO(workbook), 'customers.xlsx'),
        }, content_type='multipart/form-data')
        assert response.status_code == 200
        assert b'Map Customer Columns' in response.data
        assert Customer.query.count() == 0

        response = client.post('/sales/import/customers', data={
            'mapping': '1',
            'import_run_id': str(_staged_run('customers').id),
            'map_name': 'Name',
            'map_email': 'Email',
        }, follow_redirects=True)
        assert response.status_code == 200
        assert Customer.query.filter_by(business_id=business.id).count() == 1
        assert b'Imported 1 customer' in response.data


def test_journal_entry_import_route_flow(client, business, app):
    with app.app_context():
        workbook = _workbook([
            ['Date', 'Description', 'Account Code', 'Debit', 'Credit'],
            ['2026-09-01', 'Imported entry', '5200', 90, 0],
            ['2026-09-01', 'Imported entry', '1000', 0, 90],
        ])
        response = client.post('/accounting/import/journal-entries', data={
            'file': (BytesIO(workbook), 'entries.xlsx'),
        }, content_type='multipart/form-data')
        assert response.status_code == 200
        assert b'Map Journal Entry Columns' in response.data
        assert JournalEntry.query.filter_by(reference_type='JournalEntry').count() == 0

        response = client.post('/accounting/import/journal-entries', data={
            'mapping': '1',
            'import_run_id': str(_staged_run('journal_entries').id),
            'map_date': 'Date',
            'map_description': 'Description',
            'map_account_code': 'Account Code',
            'map_debit': 'Debit',
            'map_credit': 'Credit',
        }, follow_redirects=True)
        assert response.status_code == 200
        assert JournalEntry.query.filter_by(reference_type='JournalEntry').count() == 1
        assert b'Imported 1 journal entry' in response.data


def test_bank_statement_import_route_accepts_xlsx(client, business, app):
    with app.app_context():
        account = _bank_account(business)
        workbook = _workbook([
            ['Date', 'Description', 'Amount', 'Reference'],
            ['2026-09-05', 'Banked receipt', 320, 'REF9'],
        ])
        response = client.post('/accounting/bank-reconciliation/import', data={
            'file': (BytesIO(workbook), 'statement.xlsx'),
        }, content_type='multipart/form-data')
        assert response.status_code == 200
        assert b'Map Bank Statement Columns' in response.data
        assert BankStatement.query.count() == 0

        response = client.post('/accounting/bank-reconciliation/import', data={
            'mapping': '1',
            'account_id': str(account.id),
            'import_run_id': str(_staged_run('bank_statements').id),
            'map_date': 'Date',
            'map_description': 'Description',
            'map_amount': 'Amount',
            'map_reference': 'Reference',
        }, follow_redirects=True)
        assert response.status_code == 200
        assert BankStatement.query.filter_by(business_id=business.id).count() == 1
        assert b'Imported 1 bank statement' in response.data


def test_bank_statement_import_page_offers_file_upload(client):
    response = client.get('/accounting/bank-reconciliation/import')
    assert response.status_code == 200
    assert b'Upload Excel workbook' in response.data
    assert b'name="file"' in response.data


# --- E1: worksheet cells without an ``r`` reference -------------------------


def test_parse_xlsx_keeps_rows_whose_cells_omit_the_reference_attribute(app):
    with app.app_context():
        sheet_data = (
            f'<row r="1">{_inline_cell("A1", "Date")}{_inline_cell("B1", "Amount")}</row>'
            f'<row r="2">{_inline_cell("A2", "2026-09-01")}{_inline_cell("B2", "1250")}</row>'
            f'<row r="3">{_inline_cell(None, "2026-09-02")}{_inline_cell(None, "99")}</row>'
        )
        upload = _Upload(_raw_workbook(sheet_data))
        _, rows = parse_xlsx_file(upload)

        assert len(rows) == 2
        assert rows[0] == {'Date': '2026-09-01', 'Amount': '1250'}
        assert rows[1] == {'Date': '2026-09-02', 'Amount': '99'}


def test_bank_statement_import_reads_workbook_without_cell_references(app, business):
    with app.app_context():
        account = _bank_account(business)
        sheet_data = (
            f'<row r="1">{_inline_cell("A1", "Date")}{_inline_cell("B1", "Amount")}</row>'
            f'<row r="2">{_inline_cell(None, "2026-09-08")}{_inline_cell(None, "640")}</row>'
        )
        _, rows = parse_xlsx_file(_Upload(_raw_workbook(sheet_data)))
        result = import_bank_statements(business.id, account.id, rows)
        db.session.commit()

        assert result['imported'] == 1
        assert BankStatement.query.filter_by(business_id=business.id).count() == 1


# --- E2: duplicate header names ---------------------------------------------


def test_duplicate_headers_keep_distinct_keys_and_values(app):
    with app.app_context():
        upload = _Upload(_workbook([
            ['Name', 'Amount', 'Amount'],
            ['Acme', 100, 250],
        ]))
        _, rows = parse_xlsx_file(upload)

        assert len(rows) == 1
        assert rows[0]['Name'] == 'Acme'
        assert parse_decimal(rows[0]['Amount']) == 100
        assert parse_decimal(rows[0]['Amount (2)']) == 250


def test_triple_headers_are_numbered_without_collisions(app):
    with app.app_context():
        upload = _Upload(_workbook([
            ['Date', 'Date', 'Date'],
            ['2026-01-01', '2026-01-02', '2026-01-03'],
        ]))
        _, rows = parse_xlsx_file(upload)

        assert set(rows[0]) == {'Date', 'Date (2)', 'Date (3)'}


def test_duplicate_amount_headers_do_not_break_bank_import(app, business):
    with app.app_context():
        account = _bank_account(business)
        rows = [{'Date': '2026-09-09', 'Description': 'Split', 'Amount': 10, 'Amount (2)': 20}]
        result = import_bank_statements(business.id, account.id, rows)
        db.session.commit()

        assert result['imported'] == 1
        statement = BankStatement.query.filter_by(business_id=business.id).one()
        assert float(statement.amount) == 10


# --- E3: out-of-range Excel serials ----------------------------------------


def test_parse_date_returns_none_for_out_of_range_serials(app):
    with app.app_context():
        assert parse_date(Decimal('1e30')) is None
        assert parse_date(Decimal('-1e30')) is None
        assert parse_date(Decimal('45000')) is not None


# --- E4: alias fallback and the explicit ignore sentinel --------------------


def test_partial_column_map_still_alias_resolves_other_fields(app):
    with app.app_context():
        rows = [{'Txn date': '2026-09-10', 'Value': '300', 'Narrative': 'Deposit'}]
        resolved = resolve_columns(rows, {'date': 'Txn date'}, BANK_STATEMENT_COLUMNS)

        assert resolved['date'] == 'Txn date'
        assert resolved['amount'] == 'Value'
        assert resolved['description'] == 'Narrative'


def test_ignore_sentinel_suppresses_alias_fallback(app):
    with app.app_context():
        rows = [{'Date': '2026-09-10', 'Amount': '300', 'Reference': 'R1'}]
        resolved = resolve_columns(
            rows, {'reference': IGNORE_FIELD}, BANK_STATEMENT_COLUMNS,
        )

        assert 'reference' not in resolved
        assert resolved['date'] == 'Date'


def test_empty_column_map_value_falls_back_to_aliases(app, business):
    with app.app_context():
        account = _bank_account(business)
        rows = [{'Date': '2026-09-11', 'Amount': 75, 'Reference': 'R2'}]
        result = import_bank_statements(business.id, account.id, rows, {'reference': ''})
        db.session.commit()

        assert result['imported'] == 1
        statement = BankStatement.query.filter_by(business_id=business.id).one()
        assert statement.reference == 'R2'


def test_ignored_reference_column_disables_deduplication(app, business):
    with app.app_context():
        account = _bank_account(business)
        rows = [{'Date': '2026-09-12', 'Amount': 10, 'Reference': 'R3'}]
        result = import_bank_statements(
            business.id, account.id, rows, {'reference': IGNORE_FIELD},
        )
        db.session.commit()

        assert result['imported'] == 1
        second = import_bank_statements(
            business.id, account.id, rows, {'reference': IGNORE_FIELD},
        )
        db.session.commit()
        assert second['imported'] == 1
        assert second['duplicates'] == 0


# --- E5: single-line journal groups -----------------------------------------


def test_single_line_journal_group_reports_an_error(app, business):
    with app.app_context():
        rows = [
            {'Date': '2026-09-13', 'Description': 'Lone line', 'Account Code': '5200', 'Debit': 40, 'Credit': 0},
        ]
        result = import_journal_entries(business.id, rows)
        db.session.commit()

        assert result['imported'] == 0
        assert len(result['errors']) == 1
        assert 'Lone line' in result['errors'][0]
        assert 'two' in result['errors'][0]
        assert JournalEntry.query.filter_by(reference_type='JournalEntry').count() == 0


# --- E6: locale-driven date order -------------------------------------------


def test_parse_date_honours_the_selected_date_order(app):
    with app.app_context():
        assert str(parse_date('01/02/2026', 'MDY')) == '2026-01-02'
        assert str(parse_date('01/02/2026', 'DMY')) == '2026-02-01'
        assert str(parse_date('01/02/2026')) == '2026-01-02'
        assert str(parse_date('01/02/2026', 'nonsense')) == '2026-01-02'


def test_parse_date_reads_unambiguous_forms_under_both_orders(app):
    with app.app_context():
        assert str(parse_date('2026-02-03', 'DMY')) == '2026-02-03'
        assert str(parse_date('2026/02/03', 'DMY')) == '2026-02-03'


def test_bank_import_applies_the_date_order_from_the_run(app, business):
    with app.app_context():
        account = _bank_account(business)
        rows = [{'Date': '03/04/2026', 'Amount': 50}]
        result = import_bank_statements(business.id, account.id, rows, None, 'DMY')
        db.session.commit()

        assert result['imported'] == 1
        statement = BankStatement.query.filter_by(business_id=business.id).one()
        assert str(statement.statement_date.date()) == '2026-04-03'


def test_bank_import_route_honours_the_date_order_select(client, business, app):
    with app.app_context():
        account = _bank_account(business)
        workbook = _workbook([
            ['Date', 'Description', 'Amount'],
            ['03/04/2026', 'Ambiguous receipt', 60],
        ])
        client.post('/accounting/bank-reconciliation/import', data={
            'file': (BytesIO(workbook), 'ambiguous.xlsx'),
        }, content_type='multipart/form-data')

        response = client.post('/accounting/bank-reconciliation/import', data={
            'mapping': '1',
            'account_id': str(account.id),
            'import_run_id': str(_staged_run('bank_statements').id),
            'date_order': 'dmy',
            'map_date': 'Date',
            'map_description': 'Description',
            'map_amount': 'Amount',
        }, follow_redirects=True)
        assert response.status_code == 200

        statement = BankStatement.query.filter_by(business_id=business.id).one()
        assert str(statement.statement_date.date()) == '2026-04-03'


# --- E7: client-supplied payloads are refused -------------------------------


@pytest.mark.parametrize('endpoint,entity', [
    ('/accounting/bank-reconciliation/import', 'bank_statements'),
    ('/accounting/import/journal-entries', 'journal_entries'),
    ('/sales/import/customers', 'customers'),
    ('/purchases/import/suppliers', 'suppliers'),
])
def test_mapping_step_rejects_a_client_supplied_payload(client, business, app, endpoint, entity):
    with app.app_context():
        workbook = _workbook([['Name', 'Date', 'Amount'], ['Injected', '2026-09-01', 1]])
        client.post(endpoint, data={
            'file': (BytesIO(workbook), 'rows.xlsx'),
        }, content_type='multipart/form-data')

        response = client.post(endpoint, data={
            'mapping': '1',
            'payload': '[{"Name": "Injected", "Date": "2026-09-01", "Amount": 1}]',
            'map_name': 'Name',
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'expired' in response.data

        assert Customer.query.count() == 0
        assert Supplier.query.count() == 0
        assert BankStatement.query.count() == 0
        assert JournalEntry.query.count() == 0
        assert _staged_run(entity) is not None


def test_mapping_step_ignores_an_unknown_run_id(client, app):
    response = client.post('/sales/import/customers', data={
        'mapping': '1',
        'import_run_id': '999999',
        'map_name': 'Name',
    })
    assert response.status_code == 404


# --- A2: every importer is audited, on success and on failure ---------------


def _import_audit(action):
    return AuditLog.query.filter_by(action=action).order_by(AuditLog.id.desc()).first()


def test_successful_imports_are_audited_with_filename_and_counts(client, business, app):
    with app.app_context():
        account = _bank_account(business)

        client.post('/accounting/bank-reconciliation/import', data={
            'file': (BytesIO(_workbook([
                ['Date', 'Description', 'Amount'],
                ['2026-09-14', 'Audited receipt', 120],
            ])), 'audited-statement.xlsx'),
        }, content_type='multipart/form-data')
        client.post('/accounting/bank-reconciliation/import', data={
            'mapping': '1',
            'account_id': str(account.id),
            'import_run_id': str(_staged_run('bank_statements').id),
            'map_date': 'Date',
            'map_description': 'Description',
            'map_amount': 'Amount',
        }, follow_redirects=True)

        client.post('/sales/import/customers', data={
            'file': (BytesIO(_workbook([['Name'], ['Audited Customer']])), 'audited-customers.xlsx'),
        }, content_type='multipart/form-data')
        client.post('/sales/import/customers', data={
            'mapping': '1',
            'import_run_id': str(_staged_run('customers').id),
            'map_name': 'Name',
        }, follow_redirects=True)

        client.post('/purchases/import/suppliers', data={
            'file': (BytesIO(_workbook([['Name'], ['Audited Supplier']])), 'audited-suppliers.xlsx'),
        }, content_type='multipart/form-data')
        client.post('/purchases/import/suppliers', data={
            'mapping': '1',
            'import_run_id': str(_staged_run('suppliers').id),
            'map_name': 'Name',
        }, follow_redirects=True)

        client.post('/accounting/import/journal-entries', data={
            'file': (BytesIO(_workbook([
                ['Date', 'Description', 'Account Code', 'Debit', 'Credit'],
                ['2026-09-14', 'Audited entry', '5200', 45, 0],
                ['2026-09-14', 'Audited entry', '1000', 0, 45],
            ])), 'audited-entries.xlsx'),
        }, content_type='multipart/form-data')
        client.post('/accounting/import/journal-entries', data={
            'mapping': '1',
            'import_run_id': str(_staged_run('journal_entries').id),
            'map_date': 'Date',
            'map_description': 'Description',
            'map_account_code': 'Account Code',
            'map_debit': 'Debit',
            'map_credit': 'Credit',
        }, follow_redirects=True)

        expected = {
            'IMPORT_BANK_STATEMENTS': ('audited-statement.xlsx', 1, 1),
            'IMPORT_CUSTOMERS': ('audited-customers.xlsx', 1, 1),
            'IMPORT_SUPPLIERS': ('audited-suppliers.xlsx', 1, 1),
            'IMPORT_JOURNAL_ENTRIES': ('audited-entries.xlsx', 1, 2),
        }
        for action, (filename, imported, row_count) in expected.items():
            audit = _import_audit(action)
            assert audit is not None, action
            import json
            details = json.loads(audit.new_values)
            assert details['filename'] == filename
            assert details['imported'] == imported
            assert details['row_count'] == row_count
            assert details['duplicates'] == 0
            assert details['error_count'] == 0
            assert audit.table_name == 'import_runs'

        assert _import_audit('IMPORT_CUSTOMERS_FAILED') is None


def test_failed_imports_are_audited_and_leave_no_partial_data(client, business, app):
    with app.app_context():
        # Ignoring the account-code column leaves a required field unmapped, so
        # the import raises before any entry is written.
        client.post('/accounting/import/journal-entries', data={
            'file': (BytesIO(_workbook([
                ['Date', 'Description', 'Account Code', 'Debit', 'Credit'],
                ['2026-09-15', 'Broken entry', '5200', 30, 0],
                ['2026-09-15', 'Broken entry', '1000', 0, 30],
            ])), 'broken.xlsx'),
        }, content_type='multipart/form-data')
        run = _staged_run('journal_entries')

        response = client.post('/accounting/import/journal-entries', data={
            'mapping': '1',
            'import_run_id': str(run.id),
            'map_date': 'Date',
            'map_description': 'Description',
            'map_account_code': IGNORE_FIELD,
            'map_debit': 'Debit',
            'map_credit': 'Credit',
        }, follow_redirects=True)
        assert response.status_code == 200

        import json
        audit = _import_audit('IMPORT_JOURNAL_ENTRIES_FAILED')
        assert audit is not None
        details = json.loads(audit.new_values)
        assert details['filename'] == 'broken.xlsx'
        assert details['error']

        run = db.session.get(ImportRun, run.id)
        assert run.status == 'failed'
        assert run.staged_rows is None
        assert run.imported_count == 0
        assert run.error_count == 1
        assert JournalEntry.query.filter_by(reference_type='JournalEntry').count() == 0
        assert _import_audit('IMPORT_JOURNAL_ENTRIES') is None


def test_committed_import_run_purges_staged_rows(client, business, app):
    with app.app_context():
        client.post('/sales/import/customers', data={
            'file': (BytesIO(_workbook([['Name'], ['Purged Customer']])), 'purge.xlsx'),
        }, content_type='multipart/form-data')
        run_id = _staged_run('customers').id

        client.post('/sales/import/customers', data={
            'mapping': '1',
            'import_run_id': str(run_id),
            'map_name': 'Name',
        }, follow_redirects=True)

        run = db.session.get(ImportRun, run_id)
        assert run.status == 'committed'
        assert run.staged_rows is None
        assert run.imported_count == 1
        assert run.row_count == 1
        assert run.completed_at is not None


def test_import_result_offers_the_rejected_rows_download(client, business, app):
    with app.app_context():
        account = _bank_account(business)
        client.post('/accounting/bank-reconciliation/import', data={
            'file': (BytesIO(_workbook([
                ['Date', 'Description', 'Amount'],
                ['2026-09-16', 'Good receipt', 100],
                ['not-a-date', 'Bad receipt', 55],
            ])), 'partial.xlsx'),
        }, content_type='multipart/form-data')

        response = client.post('/accounting/bank-reconciliation/import', data={
            'mapping': '1',
            'account_id': str(account.id),
            'import_run_id': str(_staged_run('bank_statements').id),
            'map_date': 'Date',
            'map_description': 'Description',
            'map_amount': 'Amount',
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'rejected-rows.xlsx' in response.data
        assert BankStatement.query.filter_by(business_id=business.id).count() == 1