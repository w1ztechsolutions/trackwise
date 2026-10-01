from datetime import datetime, timezone

from app.models import db
from app.models.accounting import (
    Branch,
    Business,
    CostCenter,
    ChartOfAccounts,
    JournalEntry,
)
from app.services.accounting_service import post_entry
from app.services.reports import get_general_ledger, get_trial_balance


def test_branch_and_cost_center_are_managed_per_business(client, business):
    response = client.post('/accounting/dimensions', data={
        'dimension_type': 'branch',
        'code': 'BL',
        'name': 'Blantyre',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Blantyre' in response.data

    response = client.post('/accounting/dimensions', data={
        'dimension_type': 'cost_center',
        'code': 'OPS',
        'name': 'Operations',
    }, follow_redirects=True)
    assert response.status_code == 200

    branch = Branch.query.filter_by(business_id=business.id, code='BL').one()
    center = CostCenter.query.filter_by(business_id=business.id, code='OPS').one()
    assert branch.is_active
    assert center.is_active


def test_manual_journal_entry_assigns_branch_and_cost_center(client, business):
    branch = Branch(business_id=business.id, code='LL', name='Lilongwe')
    center = CostCenter(business_id=business.id, code='ADMIN', name='Administration')
    cash = ChartOfAccounts.query.filter_by(business_id=business.id, code='1000').one()
    revenue = ChartOfAccounts.query.filter_by(business_id=business.id, code='4000').one()
    db.session.add_all([branch, center])
    db.session.commit()

    response = client.post('/accounting/journal-entries/create', data={
        'description': 'Branch opening sale',
        'entry_date': '2026-09-30',
        'branch_id': str(branch.id),
        'account_id': [str(cash.id), str(revenue.id)],
        'cost_center_id': [str(center.id), str(center.id)],
        'debit_amount': ['250', '0'],
        'credit_amount': ['0', '250'],
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'posted' in response.data.lower()

    entry = JournalEntry.query.filter_by(
        business_id=business.id,
        description='Branch opening sale',
    ).one()
    assert entry.branch_id == branch.id
    assert {line.cost_center_id for line in entry.lines} == {center.id}


def test_dimension_filters_apply_to_trial_balance_and_general_ledger(client, business):
    branch_one = Branch(business_id=business.id, code='N', name='North')
    branch_two = Branch(business_id=business.id, code='S', name='South')
    center_one = CostCenter(business_id=business.id, code='SALES', name='Sales')
    center_two = CostCenter(business_id=business.id, code='OPS', name='Operations')
    db.session.add_all([branch_one, branch_two, center_one, center_two])
    db.session.flush()

    cash = ChartOfAccounts.query.filter_by(business_id=business.id, code='1000').one()
    revenue = ChartOfAccounts.query.filter_by(business_id=business.id, code='4000').one()
    for branch, center, amount in (
        (branch_one, center_one, 125),
        (branch_two, center_two, 300),
    ):
        post_entry(
            business.id,
            datetime(2026, 9, 30, tzinfo=timezone.utc),
            f'{branch.name} sale',
            [
                {'account_id': cash.id, 'debit_amount': amount, 'cost_center_id': center.id},
                {'account_id': revenue.id, 'credit_amount': amount, 'cost_center_id': center.id},
            ],
            branch_id=branch.id,
        )

    trial_balance = get_trial_balance(
        business.id,
        branch_id=branch_one.id,
        cost_center_id=center_one.id,
    )
    cash_row = next(row for row in trial_balance['entries'] if row['account'].id == cash.id)
    assert cash_row['debit'] == 125
    assert trial_balance['total_debits'] == 125
    assert trial_balance['total_credits'] == 125

    ledger = get_general_ledger(
        business.id,
        branch_id=branch_one.id,
        cost_center_id=center_one.id,
    )
    assert [row['description'] for row in ledger['entries']] == [
        'North sale',
        'North sale',
    ]
    assert all(row['branch'].id == branch_one.id for row in ledger['entries'])
    assert all(row['cost_center'].id == center_one.id for row in ledger['entries'])

    branch_one.is_active = False
    center_one.is_active = False
    db.session.commit()
    response = client.get(
        f'/reports/trial-balance?branch_id={branch_one.id}&cost_center_id={center_one.id}'
    )
    assert response.status_code == 200


def test_dimension_report_filters_reject_other_business_ids(client, business):
    other_business = Business(name='Another Business')
    db.session.add(other_business)
    db.session.flush()
    other_business_branch = Branch(
        business_id=other_business.id,
        code='X',
        name='Not this business',
    )
    db.session.add(other_business_branch)
    db.session.commit()

    response = client.get(f'/reports/general-ledger?branch_id={other_business_branch.id}')
    assert response.status_code == 404
