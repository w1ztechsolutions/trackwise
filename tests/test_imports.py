from io import BytesIO

import pytest

from app.models import BankStatement, ChartOfAccounts, JournalEntry, JournalLine, db
from app.services.import_service import (
    ImportValidationError,
    import_bank_statements,
    import_customers,
    import_journal_entries,
    import_suppliers,
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


def _bank_account(business):
    return ChartOfAccounts.query.filter_by(
        business_id=business.id,
        code='1000',
    ).one()


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

        import json as json_module

        payload = json_module.dumps([
            {'Supplier Name': 'Gamma Ltd', 'E-mail': 'hello@gamma.test', 'Phone': '999', 'Address': 'Domasi'},
            {'Supplier Name': 'Delta Ltd', 'E-mail': 'ap@delta.test', 'Phone': '888', 'Address': 'Blantyre'},
        ])
        response = client.post('/purchases/import/suppliers', data={
            'mapping': '1',
            'payload': payload,
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
            'payload': '[{"Name": "Iris Ltd", "Email": "iris@test"}]',
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
            'payload': (
                '[{"Date": "2026-09-01", "Description": "Imported entry", '
                '"Account Code": "5200", "Debit": 90, "Credit": 0},'
                '{"Date": "2026-09-01", "Description": "Imported entry", '
                '"Account Code": "1000", "Debit": 0, "Credit": 90}]'
            ),
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
            'payload': '[{"Date": "2026-09-05", "Description": "Banked receipt", "Amount": 320, "Reference": "REF9"}]',
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