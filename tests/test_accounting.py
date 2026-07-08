import unittest
from datetime import datetime, timezone
from flask import Flask
from models import db, Product, User
from services.fifo_service import record_purchase, record_sale, record_expense
from app.services.accounting_service import (
    AccountingException,
    post_entry,
    get_ledger_balances,
    get_account_by_code,
)
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
        
        p = Product(sku='PROD001', name='Widget', default_selling_price=200.0)
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


if __name__ == '__main__':
    unittest.main()
