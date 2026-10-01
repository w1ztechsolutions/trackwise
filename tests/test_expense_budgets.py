from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

from app.models import ChartOfAccounts, ExpenseBudget, JournalEntry, JournalLine, db
from app.services.reports import get_expense_budget_variance, set_expense_budget


def _post_expense(business_id, account_id, amount, entry_date, is_deleted=False):
    entry = JournalEntry(
        business_id=business_id,
        entry_date=entry_date,
        description='Budget variance test expense',
        is_deleted=is_deleted,
    )
    db.session.add(entry)
    db.session.flush()
    db.session.add(JournalLine(
        journal_entry_id=entry.id,
        account_id=account_id,
        debit_amount=amount,
        credit_amount=0,
    ))


def test_monthly_expense_budget_variance_and_account_scope(app, business):
    with app.app_context():
        rent = ChartOfAccounts.query.filter_by(
            business_id=business.id,
            code='5100',
        ).one()
        set_expense_budget(
            business.id,
            rent.id,
            date(2026, 9, 1),
            Decimal('1000.00'),
        )
        set_expense_budget(
            business.id,
            rent.id,
            date(2026, 9, 1),
            Decimal('900.00'),
        )
        _post_expense(business.id, rent.id, 950, datetime(2026, 9, 30, 23, 59))
        _post_expense(business.id, rent.id, 200, datetime(2026, 10, 1))
        _post_expense(business.id, rent.id, 300, datetime(2026, 9, 15), is_deleted=True)
        db.session.commit()

        result = get_expense_budget_variance(business.id, date(2026, 9, 1))
        rent_row = next(row for row in result['rows'] if row['account'].id == rent.id)

        assert ExpenseBudget.query.filter_by(
            business_id=business.id,
            account_id=rent.id,
            period_start=date(2026, 9, 1),
        ).count() == 1
        assert rent_row['budget'] == Decimal('900.00')
        assert rent_row['actual'] == Decimal('950.00')
        assert rent_row['variance'] == Decimal('-50.00')
        assert rent_row['percent_used'] == Decimal('950.00') / Decimal('900.00') * 100
        assert result['total_variance'] == result['total_budget'] - result['total_actual']


def test_budget_rejects_invalid_accounts_amounts_and_months(app, business):
    with app.app_context():
        rent = ChartOfAccounts.query.filter_by(
            business_id=business.id,
            code='5100',
        ).one()
        cogs = ChartOfAccounts.query.filter_by(
            business_id=business.id,
            code='5000',
        ).one()

        for account_id, period, amount in (
            (rent.id, date(2026, 9, 2), 10),
            (rent.id, date(2026, 9, 1), -1),
            (rent.id, date(2026, 9, 1), '10.001'),
            (rent.id, date(2026, 9, 1), '1000000000000'),
            (cogs.id, date(2026, 9, 1), 10),
        ):
            try:
                set_expense_budget(business.id, account_id, period, amount)
            except ValueError:
                pass
            else:
                raise AssertionError('Invalid budget input should be rejected.')


def test_budget_variance_page_saves_budgets_and_exports_xlsx(client, business, app):
    response = client.get('/reports/expense-budget-variance?period=2026-09')
    assert response.status_code == 200
    assert b'Expense Budget Variance' in response.data

    with app.app_context():
        rent = ChartOfAccounts.query.filter_by(
            business_id=business.id,
            code='5100',
        ).one()
        response = client.post(
            '/reports/expense-budget-variance',
            data={
                'period': '2026-09',
                'account_id': str(rent.id),
                'amount': '750.00',
            },
        )
        assert response.status_code == 302
        assert ExpenseBudget.query.filter_by(
            business_id=business.id,
            account_id=rent.id,
            period_start=date(2026, 9, 1),
        ).one().amount == Decimal('750.00')

    response = client.get('/reports/expense-budget-variance/export.xlsx?period=2026-09')
    assert response.status_code == 200
    assert response.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert response.headers['Content-Disposition'].endswith(
        'filename=expense-budget-variance-2026-09.xlsx'
    )
    with ZipFile(BytesIO(response.data)) as workbook:
        assert workbook.testzip() is None
        for filename in workbook.namelist():
            if filename.endswith('.xml') or filename.endswith('.rels'):
                ElementTree.fromstring(workbook.read(filename))
        sheet = ElementTree.fromstring(workbook.read('xl/worksheets/sheet1.xml'))
        cells = [cell.text for cell in sheet.iter() if cell.tag.endswith('}t')]
        assert 'Budget Variance' in workbook.read('xl/workbook.xml').decode()
        assert 'Rent Expense' in cells
        assert 'Total' in cells
        numeric_cells = [cell for cell in sheet.iter() if cell.tag.endswith('}c')]
        assert any(
            cell.attrib.get('t') != 'inlineStr'
            and any(child.tag.endswith('}v') and child.text == '750.00' for child in cell)
            for cell in numeric_cells
        )
