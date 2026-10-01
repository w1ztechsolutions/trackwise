from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest

from app.models import Budget, BudgetLineItem, ChartOfAccounts, JournalEntry, JournalLine, db
from app.services.budget_service import (
    BudgetError,
    compute_actuals,
    create_budget,
    get_budget_lines,
    get_dashboard_budget_summary,
    get_monthly_budget_vs_actual,
)
from app.services.reports import (
    get_expense_budget_variance,
    get_period_comparison,
    get_revenue_budget_variance,
)
from app.services.reports.xlsx_export import create_xlsx


def _account(business_id, code):
    return ChartOfAccounts.query.filter_by(business_id=business_id, code=code).one()


def _post_line(business_id, account_id, debit, credit, entry_date):
    entry = JournalEntry(
        business_id=business_id,
        entry_date=entry_date,
        description='Budget test entry',
        is_deleted=False,
    )
    db.session.add(entry)
    db.session.flush()
    db.session.add(JournalLine(
        journal_entry_id=entry.id,
        account_id=account_id,
        debit_amount=debit,
        credit_amount=credit,
    ))
    db.session.commit()


def test_create_revenue_budget_rejects_expense_accounts(app, business):
    with app.app_context():
        sales = _account(business.id, '4000')
        rent = _account(business.id, '5100')

        budget = create_budget(
            business.id,
            'September revenue plan',
            'revenue',
            date(2026, 9, 1),
            date(2026, 9, 30),
            [{'account_id': sales.id, 'amount': '5000.00'}],
        )
        assert budget.budget_type == 'revenue'
        assert budget.lines[0].amount == Decimal('5000.00')
        assert budget.lines[0].account.code == '4000'

        with pytest.raises(BudgetError):
            create_budget(
                business.id,
                'Invalid revenue plan',
                'revenue',
                date(2026, 9, 1),
                date(2026, 9, 30),
                [{'account_id': rent.id, 'amount': '100.00'}],
            )


def test_expense_budget_rejects_cogs_and_invalid_amounts(app, business):
    with app.app_context():
        cogs = _account(business.id, '5000')
        rent = _account(business.id, '5100')

        with pytest.raises(BudgetError):
            create_budget(
                business.id, 'COGS plan', 'expense', date(2026, 9, 1), date(2026, 9, 30),
                [{'account_id': cogs.id, 'amount': '100'}],
            )
        for amount in ('-5', '10.001', '1000000000000', 'abc'):
            with pytest.raises(BudgetError):
                create_budget(
                    business.id, 'Bad plan', 'expense',
                    date(2026, 9, 1), date(2026, 9, 30),
                    [{'account_id': rent.id, 'amount': amount}],
                )
        with pytest.raises(BudgetError):
            create_budget(
                business.id, 'Reversed period', 'expense',
                date(2026, 9, 30), date(2026, 9, 1),
                [{'account_id': rent.id, 'amount': '10'}],
            )


def test_duplicate_budget_lines_are_rejected(app, business):
    with app.app_context():
        rent = _account(business.id, '5100')
        with pytest.raises(BudgetError):
            create_budget(
                business.id, 'Duplicate lines', 'expense',
                date(2026, 9, 1), date(2026, 9, 30),
                [
                    {'account_id': rent.id, 'amount': '100'},
                    {'account_id': rent.id, 'amount': '200'},
                ],
            )
        assert Budget.query.count() == 0


def test_budget_line_uniqueness_constraint(app, business):
    with app.app_context():
        rent = _account(business.id, '5100')
        create_budget(
            business.id, 'Unique lines', 'expense',
            date(2026, 9, 1), date(2026, 9, 30),
            [{'account_id': rent.id, 'amount': '100'}],
        )
        constraint = BudgetLineItem.__table__.constraints.copy()
        assert any(
            getattr(item, 'name', None) == 'uq_budget_line_account_cost_center'
            for item in constraint
        )
        assert rent.id is not None


def test_revenue_and_expense_variance_use_correct_signs(app, business):
    with app.app_context():
        sales = _account(business.id, '4000')
        rent = _account(business.id, '5100')

        create_budget(
            business.id, 'Revenue plan', 'revenue',
            date(2026, 9, 1), date(2026, 9, 30),
            [{'account_id': sales.id, 'amount': '1000'}],
        )
        create_budget(
            business.id, 'Expense plan', 'expense',
            date(2026, 9, 1), date(2026, 9, 30),
            [{'account_id': rent.id, 'amount': '400'}],
        )
        _post_line(business.id, sales.id, 0, 750, datetime(2026, 9, 10))
        _post_line(business.id, rent.id, 460, 0, datetime(2026, 9, 12))
        _post_line(business.id, rent.id, 40, 0, datetime(2026, 9, 30, 23, 59))
        _post_line(business.id, rent.id, 999, 0, datetime(2026, 10, 1))

        revenue = get_revenue_budget_variance(business.id, date(2026, 9, 1))
        revenue_row = next(row for row in revenue['rows'] if row['account'].id == sales.id)
        assert revenue_row['actual'] == Decimal('750.00')
        assert revenue_row['variance'] == Decimal('250.00')
        assert revenue['total_actual'] == Decimal('750.00')

        expense = get_expense_budget_variance(business.id, date(2026, 9, 1))
        expense_row = next(row for row in expense['rows'] if row['account'].id == rent.id)
        assert expense_row['actual'] == Decimal('500.00')
        assert expense_row['variance'] == Decimal('-100.00')
        assert cogs_excluded(expense, business.id)


def cogs_excluded(expense, business_id):
    cogs = _account(business_id, '5000')
    return all(row['account'].id != cogs.id for row in expense['rows'])


def test_budget_lines_report_actuals(app, business):
    with app.app_context():
        rent = _account(business.id, '5100')
        budget = create_budget(
            business.id, 'Expense plan', 'expense',
            date(2026, 9, 1), date(2026, 9, 30),
            [{'account_id': rent.id, 'amount': '800.00'}],
        )
        _post_line(business.id, rent.id, 300, 0, datetime(2026, 9, 5))

        report = get_budget_lines(budget.id)
        assert report['total_budget'] == Decimal('800.00')
        assert report['total_actual'] == Decimal('300.00')
        assert report['total_variance'] == Decimal('500.00')
        assert report['rows'][0]['percent_used'] == Decimal('300.00') / Decimal('800.00') * 100


def test_compute_actuals_respects_cost_centers(app, business):
    from app.models.accounting import CostCenter

    with app.app_context():
        rent = _account(business.id, '5100')
        center = CostCenter(business_id=business.id, code='CC1', name='Head office')
        other = CostCenter(business_id=business.id, code='CC2', name='Branch')
        db.session.add_all([center, other])
        db.session.commit()

        for amount, target in ((100, center), (250, other)):
            entry = JournalEntry(
                business_id=business.id,
                entry_date=datetime(2026, 9, 8),
                description='Cost center expense',
            )
            db.session.add(entry)
            db.session.flush()
            db.session.add(JournalLine(
                journal_entry_id=entry.id,
                account_id=rent.id,
                cost_center_id=target.id,
                debit_amount=amount,
                credit_amount=0,
            ))
        db.session.commit()

        assert compute_actuals(
            business.id, [rent.id], date(2026, 9, 1), date(2026, 9, 30),
            cost_center_id=center.id,
        ) == {rent.id: Decimal('100')}
        assert compute_actuals(
            business.id, [rent.id], date(2026, 9, 1), date(2026, 9, 30),
        ) == {rent.id: Decimal('350')}


def test_period_comparison_reports_change_between_periods(app, business):
    with app.app_context():
        rent = _account(business.id, '5100')
        _post_line(business.id, rent.id, 400, 0, datetime(2026, 8, 10))
        _post_line(business.id, rent.id, 600, 0, datetime(2026, 9, 10))

        result = get_period_comparison(business.id, [rent.id], [
            (date(2026, 8, 1), date(2026, 8, 31)),
            (date(2026, 9, 1), date(2026, 9, 30)),
        ])
        assert result['periods'][0]['total_actual'] == Decimal('400')
        assert result['periods'][1]['total_actual'] == Decimal('600')
        assert result['periods'][1]['change'] == Decimal('200')
        assert result['periods'][1]['percent_change'] == Decimal('50')


def test_monthly_budget_vs_actual_wraps_both_types(app, business):
    with app.app_context():
        sales = _account(business.id, '4000')
        rent = _account(business.id, '5100')
        create_budget(
            business.id, 'Revenue plan', 'revenue',
            date(2026, 9, 1), date(2026, 9, 30),
            [{'account_id': sales.id, 'amount': '1000'}],
        )
        create_budget(
            business.id, 'Expense plan', 'expense',
            date(2026, 9, 1), date(2026, 9, 30),
            [{'account_id': rent.id, 'amount': '500'}],
        )

        summary = get_monthly_budget_vs_actual(business.id, date(2026, 9, 1))
        assert summary['total_budget'] == Decimal('1500')
        assert summary['expense']['total_budget'] == Decimal('500')
        assert summary['revenue']['total_budget'] == Decimal('1000')


def test_dashboard_budget_summary_covers_six_months(app, business):
    with app.app_context():
        rent = _account(business.id, '5100')
        for month in (7, 8, 9):
            create_budget(
                business.id, f'Expense plan {month}', 'expense',
                date(2026, month, 1), date(2026, month, 28 if month == 2 else 30),
                [{'account_id': rent.id, 'amount': '1000'}],
            )
        _post_line(business.id, rent.id, 250, 0, datetime(2026, 8, 3))

        summary = get_dashboard_budget_summary(business.id, date(2026, 9, 1), months=6)
        assert len(summary['labels']) == 6
        assert summary['actuals'][5] == 0.0
        assert summary['budgets'][5] == 1000.0
        assert summary['utilization'][6 - 1] is not None


def _workbook_bytes(rows, sheet_name='Sheet1'):
    return create_xlsx(rows, sheet_name=sheet_name).getvalue()


def _read_sheet(data):
    with ZipFile(BytesIO(data)) as workbook:
        assert workbook.testzip() is None
        for filename in workbook.namelist():
            if filename.endswith('.xml') or filename.endswith('.rels'):
                ElementTree.fromstring(workbook.read(filename))
        sheet = ElementTree.fromstring(workbook.read('xl/worksheets/sheet1.xml'))
    return sheet


def test_budget_template_download_lists_accounts(client, business):
    response = client.get('/reports/budget-variance/template.xlsx')
    assert response.status_code == 200
    assert response.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert response.headers['Content-Disposition'].endswith(
        'filename=budget-import-template.xlsx'
    )
    _read_sheet(response.data)


def test_budget_page_renders_and_saves_budget(client, business, app):
    response = client.get('/reports/budget-variance?period=2026-09')
    assert response.status_code == 200
    assert b'Budget vs Actual' in response.data
    assert b'Revenue' in response.data

    with app.app_context():
        rent = _account(business.id, '5100')
        response = client.post('/reports/budget-variance', data={
            'period': '2026-09',
            'name': 'September expenses',
            'budget_type': 'expense',
            'period_start': '2026-09-01',
            'period_end': '2026-09-30',
            'status': 'approved',
            f'amounts[{rent.id}]': '1250.00',
        })
        assert response.status_code == 302
        budget = Budget.query.filter_by(name='September expenses').one()
        assert budget.status == 'approved'
        assert budget.lines[0].amount == Decimal('1250.00')

        line = budget.lines[0]
        response = client.post(
            f'/reports/budget-variance/lines/{line.id}',
            data={'budget_id': str(budget.id), 'amount': '1500.00', 'period': '2026-09'},
        )
        assert response.status_code == 302
        assert line.amount == Decimal('1500.00')


def test_budget_page_rejects_invalid_budget(client, business, app):
    with app.app_context():
        rent = _account(business.id, '5100')
        response = client.post('/reports/budget-variance', data={
            'period': '2026-09',
            'name': 'Bad plan',
            'budget_type': 'expense',
            'period_start': '2026-09-01',
            'period_end': '2026-09-30',
            f'amounts[{rent.id}]': '-10',
        }, follow_redirects=True)
        assert response.status_code == 200
        assert Budget.query.count() == 0
        assert b'cannot be negative' in response.data


def test_budget_xlsx_import_creates_budgets(client, business, app):
    with app.app_context():
        workbook = _workbook_bytes([
            ['Account Code', 'Account Name', 'Budget Type', 'Amount', 'Cost Center Code'],
            ['5100', 'Rent Expense', 'expense', 900, ''],
            ['4000', 'Sales Revenue', 'revenue', 4200, ''],
        ])
        response = client.post('/reports/budget-variance/import', data={
            'name': 'Imported plan',
            'period_start': '2026-09-01',
            'period_end': '2026-09-30',
            'file': (BytesIO(workbook), 'budget.xlsx'),
        }, content_type='multipart/form-data')
        assert response.status_code == 302

        expense_budget = Budget.query.filter_by(budget_type='expense').one()
        revenue_budget = Budget.query.filter_by(budget_type='revenue').one()
        assert expense_budget.lines[0].amount == Decimal('900')
        assert revenue_budget.lines[0].amount == Decimal('4200')
        assert expense_budget.name == 'Imported plan (Expense)'


def test_budget_xlsx_import_rejects_unknown_and_mistyped_accounts(client, business, app):
    with app.app_context():
        workbook = _workbook_bytes([
            ['Account Code', 'Account Name', 'Budget Type', 'Amount', 'Cost Center Code'],
            ['9999', 'Missing', 'expense', 100, ''],
        ])
        response = client.post('/reports/budget-variance/import', data={
            'name': 'Bad import',
            'period_start': '2026-09-01',
            'period_end': '2026-09-30',
            'file': (BytesIO(workbook), 'budget.xlsx'),
        }, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        assert b'9999' in response.data
        assert Budget.query.count() == 0

        workbook = _workbook_bytes([
            ['Account Code', 'Account Name', 'Budget Type', 'Amount', 'Cost Center Code'],
            ['4000', 'Sales Revenue', 'expense', 100, ''],
        ])
        response = client.post('/reports/budget-variance/import', data={
            'name': 'Mistyped',
            'period_start': '2026-09-01',
            'period_end': '2026-09-30',
            'file': (BytesIO(workbook), 'budget.xlsx'),
        }, content_type='multipart/form-data', follow_redirects=True)
        assert b'revenue account' in response.data
        assert Budget.query.count() == 0


def test_budget_variance_export_contains_both_sections(client, business, app):
    with app.app_context():
        sales = _account(business.id, '4000')
        rent = _account(business.id, '5100')
        create_budget(
            business.id, 'Revenue plan', 'revenue',
            date(2026, 9, 1), date(2026, 9, 30),
            [{'account_id': sales.id, 'amount': '1000'}],
        )
        create_budget(
            business.id, 'Expense plan', 'expense',
            date(2026, 9, 1), date(2026, 9, 30),
            [{'account_id': rent.id, 'amount': '600'}],
        )

        response = client.get('/reports/budget-variance/export.xlsx?period=2026-09')
        assert response.status_code == 200
        assert response.headers['Content-Disposition'].endswith(
            'filename=budget-variance-2026-09.xlsx'
        )
        sheet = _read_sheet(response.data)
        cells = [cell.text for cell in sheet.iter() if cell.tag.endswith('}t')]
        assert 'Revenue' in cells
        assert 'Expense' in cells
        assert 'Sales Revenue' in cells
        assert 'Rent Expense' in cells


def test_generic_export_route_supports_budget_variance(client, business):
    response = client.get(
        '/reports/budget-variance/export.xlsx?period=2026-09'
    )
    assert response.status_code == 200