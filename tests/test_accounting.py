import unittest
from datetime import date, datetime, timedelta, timezone
from flask import Flask
from models import db, Product, User
from services.fifo_service import record_purchase, record_sale, record_expense
from app.services.accounting_service import (
    AccountingException,
    post_entry,
    reverse_entry,
    get_ledger_balances,
    get_account_by_code,
)
from app.services.period_service import PeriodClosedError, assert_period_open, close_period
from app.services.revenue_recognition_service import (
    RevenueRecognitionError,
    create_revenue_schedule,
    recognize_revenue,
)
from app.services.audit_service import AuditLogImmutableError, record_user_action
from app.models.accounting import Business, ChartOfAccounts, JournalEntry, JournalLine, AuditLog


class TestAccountingEngine(unittest.TestCase):
    
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        self.app.config['SECRET_KEY'] = 'test'
        db.init_app(self.app)
        
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.business = Business(name='Test Business', currency='MWK')
        db.session.add(self.business)
        db.session.flush()
        
        self.user = User(email='test@test.com', role='admin', business_id=self.business.id)
        self.user.set_password('password')
        db.session.add(self.user)
        db.session.flush()
        
        self.accounts = {
            '1000': ChartOfAccounts(business_id=self.business.id, code='1000', name='Cash', type='asset'),
            '1200': ChartOfAccounts(business_id=self.business.id, code='1200', name='AR', type='asset'),
            '1400': ChartOfAccounts(business_id=self.business.id, code='1400', name='Inventory', type='asset'),
            '2100': ChartOfAccounts(business_id=self.business.id, code='2100', name='AP', type='liability'),
            '4000': ChartOfAccounts(business_id=self.business.id, code='4000', name='Revenue', type='income'),
            '5000': ChartOfAccounts(business_id=self.business.id, code='5000', name='COGS', type='expense'),
            '5100': ChartOfAccounts(business_id=self.business.id, code='5100', name='Rent Expense', type='expense'),
        }
        db.session.add_all(self.accounts.values())
        
        p = Product(sku='PROD001', name='Widget', default_selling_price=200.0, business_id=self.business.id)
        db.session.add(p)
        db.session.commit()
        self.product = p
    
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_post_entry_balanced(self):
        lines = [
            {'account_id': self.accounts['1000'].id, 'debit_amount': 500, 'credit_amount': 0},
            {'account_id': self.accounts['4000'].id, 'debit_amount': 0, 'credit_amount': 500},
        ]
        entry = post_entry(self.business.id, datetime.now(timezone.utc), 'Test entry', lines, created_by=self.user.id)
        self.assertIsInstance(entry, JournalEntry)
        self.assertEqual(entry.description, 'Test entry')
        self.assertEqual(len(entry.lines), 2)
    
    def test_post_entry_unbalanced_raises(self):
        lines = [
            {'account_id': self.accounts['1000'].id, 'debit_amount': 500, 'credit_amount': 0},
            {'account_id': self.accounts['4000'].id, 'debit_amount': 0, 'credit_amount': 300},
        ]
        with self.assertRaises(AccountingException):
            post_entry(self.business.id, datetime.now(timezone.utc), 'Bad entry', lines)
    
    def test_post_entry_missing_business_raises(self):
        lines = [
            {'account_id': self.accounts['1000'].id, 'debit_amount': 100, 'credit_amount': 0},
            {'account_id': self.accounts['4000'].id, 'debit_amount': 0, 'credit_amount': 100},
        ]
        with self.assertRaises(AccountingException):
            post_entry(None, datetime.now(timezone.utc), 'No business', lines)
    
    def test_post_entry_inactive_account_raises(self):
        self.accounts['1000'].is_active = False
        db.session.commit()
        lines = [
            {'account_id': self.accounts['1000'].id, 'debit_amount': 100, 'credit_amount': 0},
            {'account_id': self.accounts['4000'].id, 'debit_amount': 0, 'credit_amount': 100},
        ]
        with self.assertRaises(AccountingException):
            post_entry(self.business.id, datetime.now(timezone.utc), 'Inactive account', lines)
    
    def test_get_ledger_balances(self):
        lines = [
            {'account_id': self.accounts['1000'].id, 'debit_amount': 1000, 'credit_amount': 0},
            {'account_id': self.accounts['4000'].id, 'debit_amount': 0, 'credit_amount': 1000},
        ]
        post_entry(self.business.id, datetime(2026, 1, 1), 'Start', lines)
        
        balances = get_ledger_balances(self.business.id)
        cash = next(b for b in balances if b['account'].code == '1000')
        self.assertEqual(cash['balance'], 1000.0)
        
        revenue = next(b for b in balances if b['account'].code == '4000')
        self.assertEqual(revenue['balance'], -1000.0)
    
    def test_get_account_by_code(self):
        acct = get_account_by_code(self.business.id, '1000')
        self.assertIsNotNone(acct)
        self.assertEqual(acct.name, 'Cash')
    
    def test_record_purchase_posts_accounting(self):
        purchase = record_purchase(
            purchase_date=datetime(2026, 6, 1),
            supplier='Supplier X',
            notes='Test',
            items_data=[{'product_id': self.product.id, 'quantity': 10, 'unit_cost': 100.0}],
            business_id=self.business.id,
            created_by=self.user.id,
        )
        
        entry = JournalEntry.query.filter_by(reference_type='Purchase', reference_id=purchase.id).first()
        self.assertIsNotNone(entry)
        self.assertEqual(len(entry.lines), 2)
        total_debit = sum(float(l.debit_amount) for l in entry.lines)
        total_credit = sum(float(l.credit_amount) for l in entry.lines)
        self.assertAlmostEqual(total_debit, total_credit, places=2)
        self.assertAlmostEqual(total_debit, 1000.0, places=2)
    
    def test_record_sale_posts_accounting(self):
        record_purchase(
            purchase_date=datetime(2026, 6, 1),
            supplier='Supplier X',
            notes='Test',
            items_data=[{'product_id': self.product.id, 'quantity': 10, 'unit_cost': 100.0}],
            business_id=self.business.id,
            created_by=self.user.id,
        )
        
        sale = record_sale(
            sale_date=datetime(2026, 6, 2),
            customer_name='Customer Y',
            items_data=[{'product_id': self.product.id, 'quantity': 5, 'unit_price': 200.0}],
            business_id=self.business.id,
            created_by=self.user.id,
        )
        
        entry = JournalEntry.query.filter_by(reference_type='Sale', reference_id=sale.id).first()
        self.assertIsNotNone(entry)
        total_debit = sum(float(l.debit_amount) for l in entry.lines)
        total_credit = sum(float(l.credit_amount) for l in entry.lines)
        self.assertAlmostEqual(total_debit, total_credit, places=2)
        self.assertAlmostEqual(total_debit, 1500.0, places=2)
    
    def test_record_expense_posts_accounting(self):
        expense = record_expense(
            expense_date=datetime(2026, 6, 1),
            category='Rent',
            description='Office rent',
            amount=500.0,
            business_id=self.business.id,
            created_by=self.user.id,
        )
        
        entry = JournalEntry.query.filter_by(reference_type='Expense', reference_id=expense.id).first()
        self.assertIsNotNone(entry)
        total_debit = sum(float(l.debit_amount) for l in entry.lines)
        total_credit = sum(float(l.credit_amount) for l in entry.lines)
        self.assertAlmostEqual(total_debit, total_credit, places=2)
        self.assertAlmostEqual(total_debit, 500.0, places=2)
    
    def test_audit_log_created(self):
        lines = [
            {'account_id': self.accounts['1000'].id, 'debit_amount': 100, 'credit_amount': 0},
            {'account_id': self.accounts['4000'].id, 'debit_amount': 0, 'credit_amount': 100},
        ]
        entry = post_entry(
            self.business.id, datetime.now(timezone.utc), 'Audit test', lines, created_by=self.user.id
        )
        
        audit = AuditLog.query.filter_by(table_name='journal_entries', record_id=entry.id).first()
        self.assertIsNotNone(audit)
        line_audit = AuditLog.query.filter_by(
            business_id=self.business.id,
            table_name='journal_lines',
            record_id=entry.lines[0].id,
        ).first()
        self.assertIsNotNone(line_audit)

    def test_user_audit_action_is_attributed_and_immutable(self):
        record_user_action(
            self.business.id,
            self.user.id,
            'LOGIN',
            'users',
            self.user.id,
        )
        db.session.commit()

        audit = AuditLog.query.filter_by(
            business_id=self.business.id,
            user_id=self.user.id,
            action='LOGIN',
            table_name='users',
            record_id=self.user.id,
        ).one()
        audit.action = 'UPDATE'
        with self.assertRaises(AuditLogImmutableError):
            db.session.commit()
        db.session.rollback()

        audit = db.session.get(AuditLog, audit.id)
        self.assertEqual(audit.action, 'LOGIN')

    def test_reversal_posts_opposite_lines_and_preserves_original(self):
        entry = post_entry(
            self.business.id,
            datetime(2026, 6, 1, tzinfo=timezone.utc),
            'Incorrect sale',
            [
                {'account_id': self.accounts['1000'].id, 'debit_amount': 125, 'credit_amount': 0},
                {'account_id': self.accounts['4000'].id, 'debit_amount': 0, 'credit_amount': 125},
            ],
            created_by=self.user.id,
        )

        reversal = reverse_entry(
            self.business.id,
            entry.id,
            'Sale entered against the wrong customer',
            created_by=self.user.id,
            reversal_date=datetime(2026, 6, 2, tzinfo=timezone.utc),
        )

        self.assertFalse(entry.is_deleted)
        self.assertEqual(entry.reversed_by_entry_id, reversal.id)
        self.assertEqual(entry.reversal_reason, 'Sale entered against the wrong customer')
        self.assertEqual(reversal.reference_type, 'Reversal')
        self.assertEqual(reversal.reference_id, entry.id)
        self.assertEqual(
            [(line.debit_amount, line.credit_amount) for line in reversal.lines],
            [(0, 125), (125, 0)],
        )
        self.assertEqual(
            AuditLog.query.filter_by(table_name='journal_entries', record_id=entry.id).count(),
            2,
        )

    def test_reversal_requires_reason_and_cannot_be_repeated(self):
        entry = post_entry(
            self.business.id,
            datetime.now(timezone.utc),
            'Original',
            [
                {'account_id': self.accounts['1000'].id, 'debit_amount': 20, 'credit_amount': 0},
                {'account_id': self.accounts['4000'].id, 'debit_amount': 0, 'credit_amount': 20},
            ],
        )

        with self.assertRaises(AccountingException):
            reverse_entry(self.business.id, entry.id, '')

        reverse_entry(self.business.id, entry.id, 'Correction')
        with self.assertRaises(AccountingException):
            reverse_entry(self.business.id, entry.id, 'Duplicate correction')

    def test_closed_period_rejects_postings_and_allows_later_dates(self):
        close_through = datetime(2026, 6, 30).date()
        close_period(self.business.id, close_through)
        db.session.commit()

        with self.assertRaises(PeriodClosedError):
            assert_period_open(self.business.id, datetime(2026, 6, 30, 12))
        with self.assertRaises(PeriodClosedError):
            post_entry(
                self.business.id,
                datetime(2026, 6, 30),
                'Closed period entry',
                [
                    {'account_id': self.accounts['1000'].id, 'debit_amount': 50, 'credit_amount': 0},
                    {'account_id': self.accounts['4000'].id, 'debit_amount': 0, 'credit_amount': 50},
                ],
            )

        entry = post_entry(
            self.business.id,
            datetime(2026, 7, 1),
            'Open period entry',
            [
                {'account_id': self.accounts['1000'].id, 'debit_amount': 50, 'credit_amount': 0},
                {'account_id': self.accounts['4000'].id, 'debit_amount': 0, 'credit_amount': 50},
            ],
        )
        self.assertIsNotNone(entry.id)

    def test_closed_period_rejects_direct_financial_model_changes(self):
        from models import Purchase

        close_period(self.business.id, datetime(2026, 6, 30).date())
        db.session.commit()
        db.session.add(Purchase(
            business_id=self.business.id,
            purchase_date=datetime(2026, 6, 15),
            total_amount=100,
        ))

        with self.assertRaises(PeriodClosedError):
            db.session.commit()
        db.session.rollback()

    def test_deferred_revenue_is_reclassified_and_recognized_idempotently(self):
        from models import Invoice

        deferred_account = ChartOfAccounts(
            business_id=self.business.id,
            code='2300',
            name='Deferred Revenue',
            type='liability',
        )
        invoice = Invoice(
            business_id=self.business.id,
            invoice_number='INV-DEFER-001',
            invoice_date=datetime.now(timezone.utc),
            subtotal=1000,
            total_amount=1000,
            status='issued',
        )
        db.session.add_all([deferred_account, invoice])
        db.session.commit()

        record_purchase(
            purchase_date=datetime.now(timezone.utc),
            supplier='Supplier X',
            notes='Revenue schedule inventory',
            items_data=[{'product_id': self.product.id, 'quantity': 10, 'unit_cost': 100}],
            business_id=self.business.id,
            created_by=self.user.id,
        )
        sale = record_sale(
            sale_date=datetime.now(timezone.utc),
            customer_name='Customer X',
            items_data=[{'product_id': self.product.id, 'quantity': 5, 'unit_price': 200}],
            business_id=self.business.id,
            created_by=self.user.id,
            invoice_id=invoice.id,
        )
        start_date = date.today()
        schedule = create_revenue_schedule(
            self.business.id,
            invoice.id,
            self.accounts['4000'].id,
            deferred_account.id,
            1000,
            start_date,
            start_date + timedelta(days=1),
            created_by=self.user.id,
        )

        self.assertEqual(sale.invoice_id, invoice.id)
        self.assertEqual(float(schedule.total_amount), 1000.0)
        self.assertEqual(
            float(JournalEntry.query.filter_by(
                reference_type='RevenueDeferral',
                reference_id=schedule.id,
            ).first().lines[0].debit_amount),
            1000.0,
        )

        entry = recognize_revenue(
            schedule.id,
            self.business.id,
            start_date,
            created_by=self.user.id,
        )
        self.assertIsNotNone(entry)
        self.assertEqual(float(schedule.recognized_amount), 500.0)
        self.assertEqual(schedule.status, 'active')
        self.assertIsNone(
            recognize_revenue(
                schedule.id,
                self.business.id,
                start_date,
                created_by=self.user.id,
            )
        )

    def test_revenue_schedule_rejects_unposted_revenue(self):
        from models import Invoice

        deferred_account = ChartOfAccounts(
            business_id=self.business.id,
            code='2300',
            name='Deferred Revenue',
            type='liability',
        )
        invoice = Invoice(
            business_id=self.business.id,
            invoice_number='INV-NO-SALE',
            invoice_date=datetime.now(timezone.utc),
            subtotal=100,
            total_amount=100,
            status='issued',
        )
        db.session.add_all([deferred_account, invoice])
        db.session.commit()

        with self.assertRaises(RevenueRecognitionError):
            create_revenue_schedule(
                self.business.id,
                invoice.id,
                self.accounts['4000'].id,
                deferred_account.id,
                100,
                date.today(),
                date.today(),
            )


if __name__ == '__main__':
    unittest.main()