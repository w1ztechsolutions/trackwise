import json
import re
from datetime import date, datetime, timedelta

_ONE_DAY = timedelta(days=1)

from app.models import Budget, ChartOfAccounts, JournalEntry, JournalLine, db
from app.services.budget_service import create_budget, month_bounds


def _chart_blocks(html):
    return {
        match.group(1): json.loads(match.group(2))
        for match in re.finditer(
            r'<script type="application/json" id="(chartData|budgetChartData)">\s*'
            r'(.*?)\s*</script>',
            html,
            re.DOTALL,
        )
    }


def _account(business_id, code):
    return ChartOfAccounts.query.filter_by(business_id=business_id, code=code).one()


def _post_expense(business, account, amount, entry_date):
    entry = JournalEntry(
        business_id=business.id,
        entry_date=entry_date,
        description='Dashboard budget test',
    )
    db.session.add(entry)
    db.session.flush()
    db.session.add(JournalLine(
        journal_entry_id=entry.id,
        account_id=account.id,
        debit_amount=amount,
        credit_amount=0,
    ))
    db.session.commit()


def test_dashboard_renders_with_budget_chart_data(client, business, app):
    with app.app_context():
        response = client.get('/dashboard')
        assert response.status_code == 200
        html = response.data.decode()

        assert 'Budget vs Actual (Current Month)' in html
        assert 'Monthly Budget Utilization Trend' in html
        assert 'budgetChartData' in html

        blocks = _chart_blocks(html)
        assert set(blocks) == {'chartData', 'budgetChartData'}
        assert blocks['budgetChartData']['accountLabels'] == []
        assert blocks['budgetChartData']['monthLabels'] == []
        assert 'No expense budgets set for this month yet.' in html


def test_dashboard_budget_charts_reflect_saved_budgets(client, business, app):
    with app.app_context():
        today = date.today()
        month_start = today.replace(day=1)
        month_end = month_bounds(month_start)[1].date() - _ONE_DAY

        rent = _account(business.id, '5100')
        utilities = _account(business.id, '5200')
        create_budget(
            business.id, 'Current plan', 'expense',
            month_start, month_end,
            [
                {'account_id': rent.id, 'amount': '1000.00'},
                {'account_id': utilities.id, 'amount': '400.00'},
            ],
        )
        _post_expense(business, rent, 250, datetime.combine(month_start, datetime.min.time()))

        html = client.get('/dashboard').data.decode()
        blocks = _chart_blocks(html)
        budget_block = blocks['budgetChartData']

        assert budget_block['accountLabels'] == ['5100 Rent Expense', '5200 Utilities Expense']
        assert budget_block['accountBudget'] == [1000.0, 400.0]
        assert budget_block['accountActual'] == [250.0, 0.0]

        assert budget_block['monthLabels'][-1] == month_start.strftime('%b %Y')
        assert budget_block['monthBudget'][-1] == 1400.0
        assert budget_block['monthActual'][-1] == 250.0
        assert budget_block['monthUtilization'][-1] == round(250.0 / 1400.0 * 100, 1)

        assert 'No expense budgets set for this month yet.' not in html
        assert 'budgetAccountChart' in html
        assert 'budgetTrendChart' in html
        assert Budget.query.count() == 1


def test_dashboard_trend_ignores_archived_budgets(client, business, app):
    with app.app_context():
        today = date.today()
        month_start = today.replace(day=1)
        rent = _account(business.id, '5100')
        budget = create_budget(
            business.id, 'Archived plan', 'expense',
            month_start, month_start,
            [{'account_id': rent.id, 'amount': '900.00'}],
            status='archived',
        )
        assert budget.status == 'archived'

        blocks = _chart_blocks(client.get('/dashboard').data.decode())
        assert blocks['budgetChartData']['accountLabels'] == []
        assert blocks['budgetChartData']['accountBudget'] == []