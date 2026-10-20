"""Phase A: expense payee type in the Payments Hub.

Covers the retailer scenario gap where operational costs (electricity,
rent paid directly, airtime) had no clean posting path: supplier payments
debit Accounts Payable and staff payments require a staff member. The
'expense' payee type debits the line item's mapped expense account
(e.g. 5200 Utilities) and credits Cash.
"""
from datetime import datetime, timezone

import pytest

from models import (
    db,
    FinancialCategory,
    LineItem,
    Payment,
    JournalEntry,
    ChartOfAccounts,
)


def _seed_category_and_line_item(business_id, account_code='5200', name='Electricity'):
    """Create an Operating Expenses category + line item mapped to an account."""
    category = FinancialCategory(
        business_id=business_id,
        name='Operating Expenses',
        code='OPEX',
    )
    db.session.add(category)
    db.session.flush()
    line_item = LineItem(
        business_id=business_id,
        category_id=category.id,
        name=name,
        code='UTIL',
        account_code=account_code,
    )
    db.session.add(line_item)
    db.session.commit()
    return category, line_item


class TestExpensePaymentAccounting:
    """Service-level: _post_payment_accounting for payee_type='expense'."""

    def test_expense_payment_debits_line_item_account(self, app, business):
        with app.app_context():
            category, line_item = _seed_category_and_line_item(business.id)

            payment = Payment(
                business_id=business.id,
                payee_type='expense',
                category_id=category.id,
                line_item_id=line_item.id,
                description='ESCOM: electricity bill for October',
                payment_date=datetime.now(timezone.utc),
                amount=15000.00,
                payment_mode='cash',
                status='pending',
            )
            db.session.add(payment)
            db.session.flush()

            from app.services.fifo_service import _post_payment_accounting
            _post_payment_accounting(
                payment_date=payment.payment_date,
                amount=15000.00,
                payment_id=payment.id,
                business_id=business.id,
                created_by=None,
                category_id=category.id,
                line_item_id=line_item.id,
                payee_type='expense',
            )
            db.session.commit()

            entry = JournalEntry.query.filter_by(
                reference_type='Payment', reference_id=payment.id
            ).first()
            assert entry is not None, 'expense payment must post a journal entry'

            debit = [l for l in entry.lines if float(l.debit_amount) > 0]
            credit = [l for l in entry.lines if float(l.credit_amount) > 0]
            assert len(debit) == 1
            assert len(credit) == 1

            util_acct = ChartOfAccounts.query.filter_by(
                business_id=business.id, code='5200'
            ).first()
            cash_acct = ChartOfAccounts.query.filter_by(
                business_id=business.id, code='1000'
            ).first()
            assert debit[0].account_id == util_acct.id, 'must debit the line item account (5200)'
            assert credit[0].account_id == cash_acct.id, 'must credit Cash'
            assert float(debit[0].debit_amount) == 15000.00

    def test_expense_payment_without_line_item_falls_back_to_other_expenses(self, app, business):
        with app.app_context():
            payment = Payment(
                business_id=business.id,
                payee_type='expense',
                description='Misc',
                payment_date=datetime.now(timezone.utc),
                amount=500.00,
                payment_mode='cash',
                status='pending',
            )
            db.session.add(payment)
            db.session.flush()

            from app.services.fifo_service import _post_payment_accounting
            _post_payment_accounting(
                payment_date=payment.payment_date,
                amount=500.00,
                payment_id=payment.id,
                business_id=business.id,
                created_by=None,
                payee_type='expense',
            )
            db.session.commit()

            entry = JournalEntry.query.filter_by(
                reference_type='Payment', reference_id=payment.id
            ).first()
            assert entry is not None
            debit = [l for l in entry.lines if float(l.debit_amount) > 0][0]
            other_acct = ChartOfAccounts.query.filter_by(
                business_id=business.id, code='5900'
            ).first()
            assert debit.account_id == other_acct.id


class TestExpensePaymentRoute:
    """Route-level: POST /payments with payee_type='expense'."""

    def test_expense_payment_creates_approved_payment_and_entry(self, client, app, business):
        with app.app_context():
            category, line_item = _seed_category_and_line_item(business.id)
            category_id, line_item_id = category.id, line_item.id

        resp = client.post('/payments', data={
            'payee_type': 'expense',
            'payee_name': 'ESCOM',
            'description': 'Electricity bill for October',
            'category_id': str(category_id),
            'line_item_id': str(line_item_id),
            'amount': '18000.00',
            'payment_mode': 'cash',
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            payment = Payment.query.filter_by(
                business_id=business.id, payee_type='expense'
            ).first()
            assert payment is not None
            assert payment.status == 'approved', 'no approval config: must auto-approve'
            assert payment.description == 'ESCOM: Electricity bill for October'
            assert float(payment.amount) == 18000.00

            entry = JournalEntry.query.filter_by(
                reference_type='Payment', reference_id=payment.id
            ).first()
            assert entry is not None, 'journal entry must be posted at approval time'
            total_debit = sum(float(l.debit_amount) for l in entry.lines)
            total_credit = sum(float(l.credit_amount) for l in entry.lines)
            assert total_debit == pytest.approx(total_credit)
            assert total_debit == pytest.approx(18000.00)

    def test_unknown_payee_type_treated_as_expense(self, client, app, business):
        with app.app_context():
            category, line_item = _seed_category_and_line_item(business.id, name='Airtime')
            category_id, line_item_id = category.id, line_item.id

        resp = client.post('/payments', data={
            'payee_type': 'banana',
            'payee_name': 'Airtel',
            'category_id': str(category_id),
            'line_item_id': str(line_item_id),
            'amount': '5000.00',
            'payment_mode': 'cash',
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            payment = Payment.query.filter_by(
                business_id=business.id, payee_type='expense'
            ).first()
            assert payment is not None, 'invalid payee type must fall back to expense'

    def test_expense_payment_still_requires_category_and_line_item(self, client, app, business):
        with app.app_context():
            before = Payment.query.filter_by(business_id=business.id).count()

        resp = client.post('/payments', data={
            'payee_type': 'expense',
            'payee_name': 'ESCOM',
            'amount': '1000.00',
            'payment_mode': 'cash',
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            after = Payment.query.filter_by(business_id=business.id).count()
            assert before == after, 'expense without category/line item must be rejected'

    def test_expense_payment_does_not_touch_accounts_payable(self, client, app, business):
        """Regression guard: the electricity bug was ESCOM booked as a supplier
        (Dr AP / Cr Cash) leaving a negative AP balance and no P&L expense."""
        with app.app_context():
            category, line_item = _seed_category_and_line_item(business.id)
            category_id, line_item_id = category.id, line_item.id

            ap_acct = ChartOfAccounts.query.filter_by(
                business_id=business.id, code='2100'
            ).first()
            before = JournalEntry.query.filter(
                JournalEntry.business_id == business.id
            ).count()

        client.post('/payments', data={
            'payee_type': 'expense',
            'payee_name': 'ESCOM',
            'category_id': str(category_id),
            'line_item_id': str(line_item_id),
            'amount': '12000.00',
            'payment_mode': 'cash',
        }, follow_redirects=True)

        with app.app_context():
            ap_entries = JournalEntry.query.filter_by(
                business_id=business.id
            ).all()
            touched_ap = any(
                line.account_id == ap_acct.id
                for e in ap_entries[before:]
                for line in e.lines
            )
            assert not touched_ap, 'expense payments must never post to Accounts Payable'
