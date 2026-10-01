from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest

from app.models import (
    ChartOfAccounts,
    JournalEntry,
    JournalLine,
    PurchaseReturn,
    db,
)
from app.services.accounting_service import (
    AccountingException,
    get_payment_refunded_amount,
    post_entry,
    reverse_payment,
)
from app.services.purchase_return_service import (
    PurchaseReturnError,
    get_bill_returnable_balance,
    get_expenditure_returns,
    process_purchase_return,
    reverse_purchase_return,
    returnable_bills,
)
from app.services.reports import get_ap_aging
from models import Bill, Payment, Supplier


def _supplier(business):
    supplier = Supplier(
        business_id=business.id,
        supplier_id='SUPP-TEST1',
        name='Return Test Supplier',
        is_active=True,
    )
    db.session.add(supplier)
    db.session.commit()
    return supplier


def _bill(business, supplier, total='1000.00', days_ago=10, status='received'):
    bill = Bill(
        business_id=business.id,
        supplier_id=supplier.id,
        bill_number=f'BILL-{supplier.supplier_id}-{days_ago}',
        bill_date=datetime.now() - timedelta(days=days_ago),
        due_date=datetime.now() + timedelta(days=20),
        subtotal=Decimal(total),
        tax_amount=Decimal('0'),
        total_amount=Decimal(total),
        status=status,
    )
    db.session.add(bill)
    db.session.commit()
    return bill


def _pay(business, bill, amount='300.00'):
    payment = Payment(
        business_id=business.id,
        supplier_id=bill.supplier_id,
        bill_id=bill.id,
        payment_date=datetime.now() - timedelta(days=1),
        amount=Decimal(amount),
        status='approved',
        payment_mode='bank_transfer',
    )
    db.session.add(payment)
    db.session.commit()
    return payment


def _account(business_id, code):
    return ChartOfAccounts.query.filter_by(business_id=business_id, code=code).one()


def _entry_lines(entry):
    return {
        (line.account.code, 'debit' if float(line.debit_amount) else 'credit'): float(
            line.debit_amount or line.credit_amount
        )
        for line in entry.lines
    }


def test_credit_note_return_posts_ap_and_expense(app, business):
    with app.app_context():
        supplier = _supplier(business)
        bill = _bill(business, supplier)

        purchase_return = process_purchase_return(
            business.id, bill.id, '250.00', 'Damaged goods', 'credit_note',
        )
        assert purchase_return.journal_entry_id is not None
        assert purchase_return.is_applied_to_ap is True

        entry = db.session.get(JournalEntry, purchase_return.journal_entry_id)
        assert _entry_lines(entry) == {('2100', 'debit'): 250.0, ('5900', 'credit'): 250.0}
        assert entry.reference_type == 'PurchaseReturn'
        assert entry.reference_id == purchase_return.id

        assert get_bill_returnable_balance(bill.id) == Decimal('750.00')
        assert PurchaseReturn.query.filter_by(bill_id=bill.id).count() == 1


def test_refund_return_posts_ap_and_cash(app, business):
    with app.app_context():
        supplier = _supplier(business)
        bill = _bill(business, supplier, total='800.00')

        purchase_return = process_purchase_return(
            business.id, bill.id, '400.00', 'Overpayment refund', 'refund',
        )
        entry = db.session.get(JournalEntry, purchase_return.journal_entry_id)
        assert _entry_lines(entry) == {('2100', 'debit'): 400.0, ('1000', 'credit'): 400.0}


def test_returns_reject_over_returning_and_invalid_input(app, business):
    with app.app_context():
        supplier = _supplier(business)
        bill = _bill(business, supplier, total='500.00')
        _pay(business, bill, '200.00')

        with pytest.raises(PurchaseReturnError):
            process_purchase_return(business.id, bill.id, '400.00', 'Too much')
        with pytest.raises(PurchaseReturnError):
            process_purchase_return(business.id, bill.id, '0', 'Nothing')
        with pytest.raises(PurchaseReturnError):
            process_purchase_return(business.id, bill.id, '-5', 'Negative')
        with pytest.raises(PurchaseReturnError):
            process_purchase_return(business.id, bill.id, '50.001', 'Too precise')
        with pytest.raises(PurchaseReturnError):
            process_purchase_return(business.id, bill.id, '50', '')
        with pytest.raises(PurchaseReturnError):
            process_purchase_return(business.id, bill.id, '50', 'Bad type', return_type='other')
        with pytest.raises(PurchaseReturnError):
            process_purchase_return(business.id, 999999, '50', 'No bill')

        assert PurchaseReturn.query.count() == 0
        assert get_bill_returnable_balance(bill.id) == Decimal('300.00')


def test_returns_account_for_approved_payments_and_previous_returns(app, business):
    with app.app_context():
        supplier = _supplier(business)
        bill = _bill(business, supplier, total='1000.00')
        _pay(business, bill, '250.00')
        process_purchase_return(business.id, bill.id, '100.00', 'First return')
        assert get_bill_returnable_balance(bill.id) == Decimal('650.00')

        pending_payment = Payment(
            business_id=business.id,
            bill_id=bill.id,
            payment_date=datetime.now(),
            amount=Decimal('200.00'),
            status='pending',
        )
        db.session.add(pending_payment)
        db.session.commit()
        assert get_bill_returnable_balance(bill.id) == Decimal('650.00')


def test_return_can_be_reversed_only_once(app, business):
    with app.app_context():
        supplier = _supplier(business)
        bill = _bill(business, supplier, total='900.00')
        purchase_return = process_purchase_return(
            business.id, bill.id, '200.00', 'Return to reverse',
        )
        entry = db.session.get(JournalEntry, purchase_return.journal_entry_id)

        reverse_purchase_return(business.id, purchase_return.id, 'Wrong return')
        assert purchase_return.is_reversed is True
        assert entry.reversal_entry is not None
        assert get_bill_returnable_balance(bill.id) == Decimal('900.00')

        with pytest.raises(PurchaseReturnError):
            reverse_purchase_return(business.id, purchase_return.id, 'Again')
        with pytest.raises(PurchaseReturnError):
            reverse_purchase_return(business.id, 999999, 'Missing')


def test_returnable_bills_excludes_fully_settled_bills(app, business):
    with app.app_context():
        supplier = _supplier(business)
        open_bill = _bill(business, supplier, total='500.00', days_ago=5)
        settled_bill = _bill(business, supplier, total='400.00', days_ago=6)
        draft_bill = _bill(business, supplier, total='400.00', days_ago=7, status='draft')
        _pay(business, settled_bill, '400.00')

        bills = {entry['bill'].id: entry for entry in returnable_bills(business.id)}
        assert open_bill.id in bills
        assert settled_bill.id not in bills
        assert draft_bill.id not in bills


def test_ap_aging_subtracts_purchase_returns(app, business):
    with app.app_context():
        supplier = _supplier(business)
        bill = _bill(business, supplier, total='1000.00', days_ago=5)

        before = get_ap_aging(business.id, datetime.now())
        row = next(item for item in before['aging_data'] if item['supplier'].id == supplier.id)
        assert row['total_balance'] == 1000.0

        process_purchase_return(business.id, bill.id, '400.00', 'Goods returned')

        after = get_ap_aging(business.id, datetime.now())
        row = next(item for item in after['aging_data'] if item['supplier'].id == supplier.id)
        assert row['total_balance'] == 600.0
        assert after['total_returns'] == 400.0

        purchase_return = PurchaseReturn.query.filter_by(bill_id=bill.id).one()
        reverse_purchase_return(business.id, purchase_return.id, 'Reinstate')
        restored = get_ap_aging(business.id, datetime.now())
        row = next(item for item in restored['aging_data'] if item['supplier'].id == supplier.id)
        assert row['total_balance'] == 1000.0


def test_expenditure_returns_report_filters(app, business):
    with app.app_context():
        supplier = _supplier(business)
        other_supplier = Supplier(
            business_id=business.id,
            supplier_id='SUPP-TEST2',
            name='Other Supplier',
            is_active=True,
        )
        db.session.add(other_supplier)
        db.session.commit()
        bill = _bill(business, supplier, total='1000.00', days_ago=3)
        other_bill = _bill(business, other_supplier, total='600.00', days_ago=4)

        process_purchase_return(business.id, bill.id, '100.00', 'Note one', 'credit_note')
        process_purchase_return(
            business.id, other_bill.id, '250.00', 'Refund two', 'refund',
            return_date=datetime.now() - timedelta(days=40),
        )

        everything = get_expenditure_returns(business.id)
        assert everything['total_amount'] == Decimal('350.00')
        assert everything['total_credit_notes'] == Decimal('100.00')
        assert everything['total_refunds'] == Decimal('250.00')

        by_type = get_expenditure_returns(business.id, return_type='refund')
        assert len(by_type['items']) == 1

        by_supplier = get_expenditure_returns(business.id, supplier_id=supplier.id)
        assert len(by_supplier['items']) == 1
        assert by_supplier['total_amount'] == Decimal('100.00')

        recent = get_expenditure_returns(
            business.id, start_date=datetime.now() - timedelta(days=10),
        )
        assert len(recent['items']) == 1
        assert recent['items'][0].reason == 'Note one'

        with pytest.raises(PurchaseReturnError):
            get_expenditure_returns(business.id, start_date='not-a-date')


def test_purchase_return_pages_and_reverse_route(client, business, app):
    with app.app_context():
        supplier = _supplier(business)
        bill = _bill(business, supplier, total='900.00', days_ago=2)

        response = client.get('/purchases/returns/new')
        assert response.status_code == 200
        assert b'New Expenditure Return' in response.data
        assert bill.bill_number.encode() in response.data

        response = client.post('/purchases/returns/new', data={
            'bill_id': str(bill.id),
            'amount': '300.00',
            'reason': 'Wrong items shipped',
            'return_type': 'credit_note',
        })
        assert response.status_code == 302
        purchase_return = PurchaseReturn.query.one()
        assert response.headers['Location'].endswith(
            f'/purchases/returns/{purchase_return.id}'
        )

        response = client.get(f'/purchases/returns/{purchase_return.id}')
        assert response.status_code == 200
        assert b'Wrong items shipped' in response.data

        response = client.get('/purchases/returns')
        assert response.status_code == 200
        assert b'Wrong items shipped' in response.data

        response = client.get('/purchases/returns?return_type=refund')
        assert response.status_code == 200
        assert b'Wrong items shipped' not in response.data

        response = client.post(
            f'/purchases/returns/{purchase_return.id}/reverse',
            data={'reason': 'Return was issued in error'},
        )
        assert response.status_code == 302
        assert purchase_return.is_reversed is True

        response = client.get('/purchases/returns/999999')
        assert response.status_code == 404


def test_purchase_return_route_rejects_invalid_submission(client, business, app):
    with app.app_context():
        supplier = _supplier(business)
        bill = _bill(business, supplier, total='300.00', days_ago=4)

        response = client.post('/purchases/returns/new', data={
            'bill_id': 'not-a-number',
            'amount': '10',
            'reason': 'Broken',
            'return_type': 'credit_note',
        }, follow_redirects=True)
        assert response.status_code == 200
        assert PurchaseReturn.query.count() == 0

        response = client.post('/purchases/returns/new', data={
            'bill_id': str(bill.id),
            'amount': '900.00',
            'reason': 'Too much',
            'return_type': 'credit_note',
        }, follow_redirects=True)
        assert response.status_code == 200
        assert PurchaseReturn.query.count() == 0


def test_expenditure_returns_report_and_export(client, business, app):
    with app.app_context():
        supplier = _supplier(business)
        bill = _bill(business, supplier, total='1000.00', days_ago=8)
        process_purchase_return(business.id, bill.id, '225.00', 'Damaged in transit')
        process_purchase_return(
            business.id, bill.id, '75.00', 'Price correction', 'refund',
        )

        response = client.get('/reports/expenditure-returns')
        assert response.status_code == 200
        assert b'Expenditure Returns' in response.data
        assert b'Damaged in transit' in response.data

        response = client.get('/reports/expenditure-returns?return_type=credit_note')
        assert response.status_code == 200
        assert b'Damaged in transit' in response.data
        assert b'Price correction' not in response.data

        response = client.get(f'/reports/expenditure-returns?supplier_id={supplier.id}')
        assert response.status_code == 200
        assert b'Damaged in transit' in response.data

        response = client.get('/reports/expenditure-returns/export.xlsx')
        assert response.status_code == 200
        assert response.headers['Content-Disposition'].endswith(
            'filename=expenditure-returns.xlsx'
        )
        with ZipFile(BytesIO(response.data)) as workbook:
            assert workbook.testzip() is None
            for filename in workbook.namelist():
                if filename.endswith('.xml') or filename.endswith('.rels'):
                    ElementTree.fromstring(workbook.read(filename))
            sheet = ElementTree.fromstring(workbook.read('xl/worksheets/sheet1.xml'))
        cells = [cell.text for cell in sheet.iter() if cell.tag.endswith('}t')]
        assert 'Damaged in transit' in cells
        assert 'Bill Credit Note' in cells
        assert 'Cash Refund' in cells

        response = client.get(
            f'/reports/expenditure-returns/export.xlsx?supplier_id={supplier.id}'
        )
        assert response.status_code == 200


def _post_payment_entry(business, payment):
    cash = _account(business.id, '1000')
    ap = _account(business.id, '2100')
    return post_entry(
        business.id,
        payment.payment_date,
        f'Payment #{payment.id}',
        [
            {'account_id': ap.id, 'debit_amount': float(payment.amount), 'credit_amount': 0},
            {'account_id': cash.id, 'debit_amount': 0, 'credit_amount': float(payment.amount)},
        ],
        reference_type='Payment',
        reference_id=payment.id,
    )


def _approved_payment(business, amount='500.00'):
    payment = Payment(
        business_id=business.id,
        payment_date=datetime.now() - timedelta(days=2),
        amount=Decimal(amount),
        status='approved',
        payment_mode='bank_transfer',
    )
    db.session.add(payment)
    db.session.commit()
    _post_payment_entry(business, payment)
    return payment


def _cash_balance(business):
    cash = _account(business.id, '1000')
    rows = db.session.query(JournalLine).join(JournalEntry).filter(
        JournalLine.account_id == cash.id,
        JournalEntry.business_id == business.id,
        JournalEntry.is_deleted.is_(False),
    ).all()
    return sum(
        float(line.debit_amount or 0) - float(line.credit_amount or 0) for line in rows
    )


def test_full_refund_reverses_payment_entry(app, business):
    with app.app_context():
        payment = _approved_payment(business)
        entry = JournalEntry.query.filter_by(
            business_id=business.id,
            reference_type='Payment',
            reference_id=payment.id,
        ).one()
        cash_before = _cash_balance(business)

        reversal = reverse_payment(business.id, payment.id, 'Duplicate payment')

        assert payment.is_reversed is True
        assert payment.reversal_reason == 'Duplicate payment'
        assert payment.reversal_date is not None
        assert entry.reversal_entry.id == reversal.id
        assert abs(_cash_balance(business) - (cash_before + 500.0)) < 0.01

        with pytest.raises(AccountingException):
            reverse_payment(business.id, payment.id, 'Again')


def test_partial_refund_posts_proportional_reversal(app, business):
    with app.app_context():
        payment = _approved_payment(business, '800.00')
        cash_before = _cash_balance(business)

        reversal = reverse_payment(
            business.id, payment.id, 'Partial settlement', amount='300.00',
        )
        assert reversal.reference_type == 'PaymentReversal'
        assert payment.is_reversed is False
        assert abs(_cash_balance(business) - (cash_before + 300.0)) < 0.01
        assert get_payment_refunded_amount(business.id, payment.id) == 300.0

        with pytest.raises(AccountingException):
            reverse_payment(business.id, payment.id, 'Too much', amount='600.00')
        with pytest.raises(AccountingException):
            reverse_payment(business.id, payment.id, 'Negative', amount='-10')

        reverse_payment(business.id, payment.id, 'Remainder', amount='500.00')
        assert get_payment_refunded_amount(business.id, payment.id) == 800.0
        assert payment.is_reversed is True

        with pytest.raises(AccountingException):
            reverse_payment(business.id, payment.id, 'Nothing left')


def test_refund_validation(app, business):
    with app.app_context():
        payment = _approved_payment(business)

        with pytest.raises(AccountingException):
            reverse_payment(business.id, payment.id, '')
        with pytest.raises(AccountingException):
            reverse_payment(business.id, payment.id, 'x' * 300)
        with pytest.raises(AccountingException):
            reverse_payment(business.id, 999999, 'Missing payment')

        payment.status = 'pending'
        db.session.commit()
        with pytest.raises(AccountingException):
            reverse_payment(business.id, payment.id, 'Not approved')

        payment.status = 'approved'
        payment.is_reversed = True
        db.session.commit()
        with pytest.raises(AccountingException):
            reverse_payment(business.id, payment.id, 'Already refunded')


def test_payment_refund_route(client, business, app):
    with app.app_context():
        payment = _approved_payment(business, '250.00')

        response = client.post(
            f'/payments/{payment.id}/refund',
            data={'reason': 'Refund agreed with supplier'},
        )
        assert response.status_code == 302
        assert payment.is_reversed is True

        response = client.post(
            f'/payments/{payment.id}/refund',
            data={'reason': 'Second attempt', 'refund_amount': '10'},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'already been refunded' in response.data

        response = client.post('/payments/999999/refund', data={'reason': 'Missing'})
        assert response.status_code == 404