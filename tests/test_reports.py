"""Tests for report services."""

import unittest
from datetime import datetime, timezone
from flask import Flask
from models import db, Product, User
from services.fifo_service import record_purchase, record_sale, record_expense
from app.services.reports import (
    get_income_statement,
    get_balance_sheet,
    get_cash_flow,
    get_trial_balance,
    get_general_ledger,
    get_ar_aging,
    get_ap_aging,
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
        
        self.user = User(email='test@test.com', role='admin', business_id=self.business.id)
        self.user.set_password('password')
        db.session.add(self.user)
        db.session.flush()
        
        # Create chart of accounts
        self.accounts = {
            '1000': ChartOfAccounts(business_id=self.business.id, code='1000', name='Cash', type='asset'),
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
        p = Product(sku='PROD001', name='Widget', default_selling_price=200.0)
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
    
    def test_ar_aging(self):
        """Test AR aging generation."""
        from models import Customer, Invoice
        
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
            invoice_date=datetime(2026, 6, 1),
            due_date=datetime(2026, 6, 30),
            subtotal=1000.0,
            total_amount=1000.0,
            status='issued',
        )
        db.session.add(invoice)
        db.session.commit()
        
        # Get AR aging
        ar = get_ar_aging(self.business.id)
        
        self.assertIn('aging_data', ar)
        self.assertIn('totals', ar)
    
    def test_ap_aging(self):
        """Test AP aging generation."""
        from models import Supplier, Bill
        
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
            bill_date=datetime(2026, 6, 1),
            due_date=datetime(2026, 6, 30),
            subtotal=1000.0,
            total_amount=1000.0,
            status='received',
        )
        db.session.add(bill)
        db.session.commit()
        
        # Get AP aging
        ap = get_ap_aging(self.business.id)
        
        self.assertIn('aging_data', ap)
        self.assertIn('totals', ap)


if __name__ == '__main__':
    unittest.main()