"""Tests for report services."""

import unittest
from datetime import datetime, timezone
from flask import Flask
from models import db, Product, Setting, User
from app.services.accounting_service import post_entry
from services.fifo_service import record_purchase, record_sale, record_expense
from app.services.reports import (
    get_income_statement,
    get_balance_sheet,
    get_cash_flow,
    get_trial_balance,
    get_general_ledger,
    get_audit_log,
    get_ar_aging,
    get_ap_aging,
    get_cashbook,
)
from app.models.accounting import Business, ChartOfAccounts, JournalEntry, JournalLine


class TestReportServices(unittest.TestCase):
    
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
        
        self.user = User(email='test@test.com', role='admin', business_id=self.business.id, name='Test User')
        self.user.set_password('password')
        db.session.add(self.user)
        db.session.flush()
        
        # Create chart of accounts
        self.accounts = {
            '1000': ChartOfAccounts(business_id=self.business.id, code='1000', name='Cash', type='asset'),
            '1100': ChartOfAccounts(business_id=self.business.id, code='1100', name='Bank', type='asset'),
            '1200': ChartOfAccounts(business_id=self.business.id, code='1200', name='AR', type='asset'),
            '1400': ChartOfAccounts(business_id=self.business.id, code='1400', name='Inventory', type='asset'),
            '2100': ChartOfAccounts(business_id=self.business.id, code='2100', name='AP', type='liability'),
            '2200': ChartOfAccounts(business_id=self.business.id, code='2200', name='Tax Payable', type='liability'),
            '3000': ChartOfAccounts(business_id=self.business.id, code='3000', name='Capital', type='equity'),
            '3100': ChartOfAccounts(business_id=self.business.id, code='3100', name='Retained Earnings', type='equity'),
            '4000': ChartOfAccounts(business_id=self.business.id, code='4000', name='Sales Revenue', type='income'),
            '5000': ChartOfAccounts(business_id=self.business.id, code='5000', name='COGS', type='expense'),
            '5100': ChartOfAccounts(business_id=self.business.id, code='5100', name='Rent Expense', type='expense'),
        }
        db.session.add_all(self.accounts.values())
        
        # Create test product
        p = Product(sku='PROD001', name='Widget', default_selling_price=200.0, business_id=self.business.id)
        db.session.add(p)
        db.session.commit()
        self.product = p
    
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_income_statement(self):
        """Test income statement generation."""
        # Record a purchase
        record_purchase(
            purchase_date=datetime(2026, 6, 1),
            supplier='Supplier X',
            notes='Test',
            items_data=[{'product_id': self.product.id, 'quantity': 10, 'unit_cost': 100.0}],
            business_id=self.business.id,
            created_by=self.user.id,
        )
        
        # Record a sale
        record_sale(
            sale_date=datetime(2026, 6, 2),
            customer_name='Customer Y',
            items_data=[{'product_id': self.product.id, 'quantity': 5, 'unit_price': 200.0}],
            business_id=self.business.id,
            created_by=self.user.id,
        )
        
        # Record an expense
        record_expense(
            expense_date=datetime(2026, 6, 3),
            category='Rent',
            description='Office rent',
            amount=500.0,
            business_id=self.business.id,
            created_by=self.user.id,
        )
        
        # Get income statement
        pl = get_income_statement(self.business.id)
        
        self.assertIn('total_revenue', pl)
        self.assertIn('total_cogs', pl)
        self.assertIn('gross_profit', pl)
        self.assertIn('total_expenses', pl)
        self.assertIn('net_profit', pl)

    def test_income_statement_uses_business_tax_rate_and_excludes_soft_deleted_entries(self):
        db.session.add(Setting(
            business_id=self.business.id,
            key='tax_rate',
            value='10',
        ))
        db.session.commit()
        post_entry(
            self.business.id,
            datetime(2026, 6, 1),
            'Recognized revenue',
            [
                {'account_id': self.accounts['1000'].id, 'debit_amount': 1000, 'credit_amount': 0},
                {'account_id': self.accounts['4000'].id, 'debit_amount': 0, 'credit_amount': 1000},
            ],
        )
        post_entry(
            self.business.id,
            datetime(2026, 6, 2),
            'Operating expense',
            [
                {'account_id': self.accounts['5100'].id, 'debit_amount': 200, 'credit_amount': 0},
                {'account_id': self.accounts['1000'].id, 'debit_amount': 0, 'credit_amount': 200},
            ],
        )
        deleted_entry = post_entry(
            self.business.id,
            datetime(2026, 6, 3),
            'Soft-deleted revenue',
            [
                {'account_id': self.accounts['1000'].id, 'debit_amount': 500, 'credit_amount': 0},
                {'account_id': self.accounts['4000'].id, 'debit_amount': 0, 'credit_amount': 500},
            ],
        )
        deleted_entry.is_deleted = True
        deleted_entry.deleted_by = self.user.id
        deleted_entry.deleted_at = datetime.now(timezone.utc)
        db.session.commit()

        pl = get_income_statement(self.business.id)

        self.assertEqual(pl['total_revenue'], 1000.0)
        self.assertEqual(pl['total_expenses'], 200.0)
        self.assertEqual(pl['tax_rate'], 10.0)
        self.assertEqual(pl['tax_amount'], 80.0)
        self.assertTrue(pl['tax_is_estimate'])
        self.assertIn('not calculated', pl['tax_note'])
    
    def test_balance_sheet(self):
        """Test balance sheet generation."""
        # Record a purchase
        record_purchase(
            purchase_date=datetime(2026, 6, 1),
            supplier='Supplier X',
            notes='Test',
            items_data=[{'product_id': self.product.id, 'quantity': 10, 'unit_cost': 100.0}],
            business_id=self.business.id,
            created_by=self.user.id,
        )
        
        # Get balance sheet
        bs = get_balance_sheet(self.business.id)
        
        self.assertIn('total_assets', bs)
        self.assertIn('assets', bs)
        self.assertIn('total_liabilities', bs)
        self.assertIn('liabilities', bs)
        self.assertIn('total_equity', bs)
        self.assertIn('equity', bs)
        self.assertIn('is_balanced', bs)
    
    def test_cash_flow(self):
        """Test cash flow statement generation."""
        # Record a purchase first (to have inventory)
        record_purchase(
            purchase_date=datetime(2026, 6, 1),
            supplier='Supplier X',
            notes='Test',
            items_data=[{'product_id': self.product.id, 'quantity': 10, 'unit_cost': 100.0}],
            business_id=self.business.id,
            created_by=self.user.id,
        )
        
        # Record a sale
        record_sale(
            sale_date=datetime(2026, 6, 2),
            customer_name='Customer Y',
            items_data=[{'product_id': self.product.id, 'quantity': 5, 'unit_price': 200.0}],
            business_id=self.business.id,
            created_by=self.user.id,
        )
        
        # Get cash flow
        cf = get_cash_flow(self.business.id)
        
        self.assertIn('operating', cf)
        self.assertIn('investing', cf)
        self.assertIn('financing', cf)
        self.assertIn('net_cash', cf)
    
    def test_trial_balance(self):
        """Test trial balance generation."""
        # Record a purchase
        record_purchase(
            purchase_date=datetime(2026, 6, 1),
            supplier='Supplier X',
            notes='Test',
            items_data=[{'product_id': self.product.id, 'quantity': 10, 'unit_cost': 100.0}],
            business_id=self.business.id,
            created_by=self.user.id,
        )
        
        # Get trial balance
        tb = get_trial_balance(self.business.id)
        
        self.assertIn('entries', tb)
        self.assertIn('total_debits', tb)
        self.assertIn('total_credits', tb)
        self.assertIn('is_balanced', tb)
        self.assertTrue(tb['is_balanced'])
    
    def test_general_ledger(self):
        """Test general ledger generation."""
        # Record a purchase
        record_purchase(
            purchase_date=datetime(2026, 6, 1),
            supplier='Supplier X',
            notes='Test',
            items_data=[{'product_id': self.product.id, 'quantity': 10, 'unit_cost': 100.0}],
            business_id=self.business.id,
            created_by=self.user.id,
        )
        
        # Get general ledger
        gl = get_general_ledger(self.business.id)
        
        self.assertIn('entries', gl)
        self.assertIn('accounts', gl)
        self.assertGreater(len(gl['entries']), 0)
        # Verify audit attribution is present
        for entry in gl['entries']:
            self.assertIn('created_by_name', entry)
            self.assertIn('created_at', entry)
        self.assertEqual(gl['entries'][0]['created_by_name'], 'Test User')

    def test_cashbook(self):
        """Test cashbook report generation."""
        # Record a purchase (credit AP — does not touch cash/bank)
        record_purchase(
            purchase_date=datetime(2026, 6, 1),
            supplier='Supplier X',
            notes='Test',
            items_data=[{'product_id': self.product.id, 'quantity': 10, 'unit_cost': 100.0}],
            business_id=self.business.id,
            created_by=self.user.id,
        )

        # Record a sale (debit Cash — cash inflow)
        record_sale(
            sale_date=datetime(2026, 6, 2),
            customer_name='Customer Y',
            items_data=[{'product_id': self.product.id, 'quantity': 5, 'unit_price': 200.0}],
            business_id=self.business.id,
            created_by=self.user.id,
        )

        # Record an expense (credit Cash — cash outflow)
        record_expense(
            expense_date=datetime(2026, 6, 3),
            category='Rent',
            description='Office rent',
            amount=500.0,
            business_id=self.business.id,
            created_by=self.user.id,
        )

        # Get cashbook (no date filter → opening balance is 0)
        cb = get_cashbook(self.business.id)

        self.assertIn('entries', cb)
        self.assertIn('total_debits', cb)
        self.assertIn('total_credits', cb)
        self.assertIn('opening_balance', cb)
        self.assertIn('closing_balance', cb)
        self.assertIn('net_cash_flow', cb)
        self.assertIn('accounts', cb)
        self.assertGreater(len(cb['entries']), 0)
        # Cash (1000) and Bank (1100) accounts are both resolved
        self.assertEqual(len(cb['accounts']), 2)

        # Verify entry fields
        for entry in cb['entries']:
            self.assertIn('date', entry)
            self.assertIn('entry_id', entry)
            self.assertIn('description', entry)
            self.assertIn('reference_type', entry)
            self.assertIn('reference_id', entry)
            self.assertIn('account_code', entry)
            self.assertIn('account_name', entry)
            self.assertIn('debit', entry)
            self.assertIn('credit', entry)
            self.assertIn('balance', entry)
            self.assertIn('created_by_name', entry)
            self.assertIn('created_at', entry)

        # Sale posts a Cash debit of 1000; expense posts a Cash credit of 500
        self.assertEqual(cb['total_debits'], 1000.0)
        self.assertEqual(cb['total_credits'], 500.0)
        self.assertEqual(cb['net_cash_flow'], 500.0)
        self.assertEqual(cb['opening_balance'], 0.0)
        self.assertEqual(cb['closing_balance'], 500.0)
        # Last running balance equals the closing balance
        self.assertEqual(cb['entries'][-1]['balance'], 500.0)
        # Audit attribution
        self.assertEqual(cb['entries'][0]['created_by_name'], 'Test User')

        # Date-range filtering affects opening/closing balances correctly
        cb_filtered = get_cashbook(
            self.business.id,
            start_date=datetime(2026, 6, 2),
            end_date=datetime(2026, 6, 3),
        )
        # Opening balance = net before June 2 (nothing) = 0
        self.assertEqual(cb_filtered['opening_balance'], 0.0)
        # Only the sale (June 2) and expense (June 3) fall in range
        self.assertEqual(len(cb_filtered['entries']), 2)
        self.assertEqual(cb_filtered['total_debits'], 1000.0)
        self.assertEqual(cb_filtered['total_credits'], 500.0)
        self.assertEqual(cb_filtered['closing_balance'], 500.0)

    def test_audit_log(self):
        """Financial business records and ledger postings appear in the audit trail."""
        db.session.info['audit_actor_id'] = self.user.id
        record_purchase(
            purchase_date=datetime(2026, 6, 1),
            supplier='Supplier X',
            notes='Test',
            items_data=[{'product_id': self.product.id, 'quantity': 10, 'unit_cost': 100.0}],
            business_id=self.business.id,
            created_by=self.user.id,
        )
        db.session.info.pop('audit_actor_id', None)
        
        al = get_audit_log(self.business.id)
        
        self.assertIn('entries', al)
        self.assertGreater(len(al['entries']), 0)
        logged_tables = {log['table_name'] for log in al['entries']}
        self.assertTrue({'purchases', 'purchase_items', 'stock_transactions', 'journal_entries'} <= logged_tables)
        self.assertTrue(all(log['action'] == 'CREATE' for log in al['entries']))
        journal_logs = [
            log for log in al['entries']
            if log['table_name'] == 'journal_entries' and log['action'] == 'CREATE'
        ]
        self.assertTrue(journal_logs)
        self.assertEqual(journal_logs[0]['user_name'], 'Test User')
    
    def test_ar_aging(self):
        """Test AR aging generation."""
        from models import Customer, Invoice, Receipt
        
        # Create a customer
        customer = Customer(
            business_id=self.business.id,
            name='Test Customer',
            is_active=True,
        )
        db.session.add(customer)
        db.session.flush()
        
        # Create an invoice
        invoice = Invoice(
            business_id=self.business.id,
            customer_id=customer.id,
            invoice_number='INV-001',
            invoice_date=datetime(2026, 8, 15),
            due_date=datetime(2026, 8, 15),
            subtotal=1000.0,
            total_amount=1000.0,
            status='partially_paid',
        )
        db.session.add(invoice)
        db.session.flush()
        db.session.add_all([
            Receipt(
                business_id=self.business.id,
                customer_id=customer.id,
                invoice_id=invoice.id,
                receipt_date=datetime(2026, 9, 10),
                amount=400.0,
                payment_method='cash',
            ),
            Receipt(
                business_id=self.business.id,
                customer_id=customer.id,
                invoice_id=invoice.id,
                receipt_date=datetime(2026, 10, 1),
                amount=100.0,
                payment_method='cash',
            ),
        ])
        db.session.commit()

        ar = get_ar_aging(self.business.id, datetime(2026, 9, 30))

        self.assertIn('aging_data', ar)
        self.assertIn('totals', ar)
        self.assertEqual(ar['totals']['total_balance'], 600.0)
        self.assertEqual(ar['totals']['days_30'], 600.0)
        self.assertEqual(sum(ar['totals'][bucket] for bucket in (
            'current', 'days_30', 'days_60', 'days_90'
        )), ar['totals']['total_balance'])
    
    def test_ap_aging(self):
        """Test AP aging generation."""
        from models import Supplier, Bill, Payment
        
        # Create a supplier
        supplier = Supplier(
            business_id=self.business.id,
            name='Test Supplier',
            is_active=True,
        )
        db.session.add(supplier)
        db.session.flush()
        
        # Create a bill
        bill = Bill(
            business_id=self.business.id,
            supplier_id=supplier.id,
            bill_number='BILL-001',
            bill_date=datetime(2026, 8, 15),
            due_date=datetime(2026, 8, 15),
            subtotal=1000.0,
            total_amount=1000.0,
            status='received',
        )
        db.session.add(bill)
        db.session.flush()
        db.session.add_all([
            Payment(
                business_id=self.business.id,
                supplier_id=supplier.id,
                bill_id=bill.id,
                payment_date=datetime(2026, 9, 10),
                amount=300.0,
                status='approved',
            ),
            Payment(
                business_id=self.business.id,
                supplier_id=supplier.id,
                bill_id=bill.id,
                payment_date=datetime(2026, 9, 10),
                amount=100.0,
                status='pending',
            ),
            Payment(
                business_id=self.business.id,
                supplier_id=supplier.id,
                bill_id=bill.id,
                payment_date=datetime(2026, 10, 1),
                amount=100.0,
                status='approved',
            ),
        ])
        db.session.commit()

        ap = get_ap_aging(self.business.id, datetime(2026, 9, 30))

        self.assertIn('aging_data', ap)
        self.assertIn('totals', ap)
        self.assertEqual(ap['totals']['total_balance'], 700.0)
        self.assertEqual(ap['totals']['days_30'], 700.0)
        self.assertEqual(sum(ap['totals'][bucket] for bucket in (
            'current', 'days_30', 'days_60', 'days_90'
        )), ap['totals']['total_balance'])


if __name__ == '__main__':
    unittest.main()