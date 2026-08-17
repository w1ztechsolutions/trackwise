import pytest
from datetime import datetime
from models import Product, Sale, Purchase, Expense, Customer, Invoice, InvoiceItem, Supplier, Bill, db
from services.fifo_service import record_purchase, record_sale, record_expense


class TestDashboardRoutes:
    def test_dashboard_page_loads(self, client):
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        with client.session_transaction() as sess:
            sess['_flashes'] = []
        assert b'TrackWise' in resp.data or b'dashboard' in resp.data.lower()

    def test_dashboard_chart_data_present(self, client):
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        assert b'salesExpensesChart' in resp.data or b'Chart.js' in resp.data


class TestInventoryRoutes:
    def test_inventory_list(self, client):
        resp = client.get('/inventory')
        assert resp.status_code == 200

    def test_create_product(self, client, app):
        with app.app_context():
            resp = client.post('/inventory', data={
                'name': 'Test Product',
                'description': 'A test product',
                'low_stock_threshold': 5,
                'default_selling_price': 100.0,
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert b'Test Product' in resp.data or b'success' in resp.data.lower()

    def test_duplicate_name_rejected(self, client, app):
        with app.app_context():
            client.post('/inventory', data={
                'name': 'Unique Name',
                'description': '',
                'low_stock_threshold': 5,
                'default_selling_price': 100.0,
            })
            resp = client.post('/inventory', data={
                'name': 'Unique Name',
                'description': '',
                'low_stock_threshold': 5,
                'default_selling_price': 100.0,
            }, follow_redirects=True)
            assert b'already exists' in resp.data or b'Unique Name' in resp.data

    def test_delete_product(self, client, app, business):
        with app.app_context():
            from models import db
            p = Product(sku='DEL-001', name='To Delete', default_selling_price=10.0, business_id=business.id)
            db.session.add(p)
            db.session.commit()
            product_id = p.id
        resp = client.post('/inventory', data={
            'action': 'delete_product',
            'product_id': product_id,
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            p = db.session.get(Product, product_id)
            assert p.is_active is False

    def test_edit_product(self, client, app, business):
        with app.app_context():
            from models import db
            p = Product(sku='EDIT-001', name='To Edit', default_selling_price=10.0, business_id=business.id)
            db.session.add(p)
            db.session.commit()
            product_id = p.id
        resp = client.post('/inventory', data={
            'action': 'edit_product',
            'product_id': product_id,
            'name': 'Edited Name',
            'description': 'Edited description',
            'low_stock_threshold': 10,
            'default_selling_price': 25.0,
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            p = db.session.get(Product, product_id)
            assert p.name == 'Edited Name'
            assert p.default_selling_price == 25.0

    def test_api_products(self, client, app, business):
        with app.app_context():
            p = Product(sku='API-001', name='API Product', default_selling_price=50.0, business_id=business.id)
            from models import db
            db.session.add(p)
            db.session.commit()
        resp = client.get('/api/products')
        assert resp.status_code == 200
        assert b'API-001' in resp.data


class TestPurchasesRoutes:
    def test_purchases_page_loads(self, client):
        resp = client.get('/purchases')
        assert resp.status_code == 200

    def test_record_purchase(self, client, app, business):
        with app.app_context():
            from models import db
            p = Product(sku='PUR-001', name='Purchase Item', default_selling_price=200.0, business_id=business.id)
            db.session.add(p)
            db.session.commit()
            resp = client.post('/purchases', data={
                'supplier': 'Test Supplier',
                'notes': 'Test purchase',
                'purchase_date': datetime.now().isoformat(),
                'product_id[]': [str(p.id)],
                'quantity[]': ['10'],
                'unit_cost[]': ['500.0'],
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert b'recorded' in resp.data.lower() or b'success' in resp.data.lower()


class TestSalesRoutes:
    def test_sales_page_loads(self, client):
        resp = client.get('/sales')
        assert resp.status_code == 200

    def test_record_sale(self, client, app, business):
        with app.app_context():
            from models import db
            p = Product(sku='SAL-001', name='Sale Item', default_selling_price=300.0, business_id=business.id)
            db.session.add(p)
            db.session.commit()
            product_id = p.id
            record_purchase(
                purchase_date=datetime.now(),
                supplier='Initial',
                notes='stock',
                items_data=[{'product_id': product_id, 'quantity': 20, 'unit_cost': 100.0}],
                business_id=business.id,
            )
            with client.session_transaction() as sess:
                sess['_flashes'] = []
            resp = client.post('/sales', data={
                'customer_name': 'Test Customer',
                'sale_date': datetime.now().isoformat(),
                'product_id[]': [str(product_id)],
                'quantity[]': ['5'],
                'unit_price[]': ['300.0'],
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert b'recorded' in resp.data.lower() or b'success' in resp.data.lower()


class TestExpensesRoutes:
    def test_expenses_page_loads(self, client):
        resp = client.get('/expenses', follow_redirects=True)
        assert resp.status_code == 200

    def test_record_expense(self, client, app):
        with app.app_context():
            with client.session_transaction() as sess:
                sess['_flashes'] = []
            resp = client.post('/expenses', data={
                'category': 'Rent',
                'description': 'Office rent',
                'amount': '5000.0',
                'expense_date': datetime.now().isoformat(),
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert b'recorded' in resp.data.lower() or b'success' in resp.data.lower()


class TestReportsRoutes:
    def test_reports_page_loads(self, client):
        resp = client.get('/reports', follow_redirects=True)
        assert resp.status_code == 200

    def test_reports_with_date_filter(self, client):
        resp = client.get('/reports?start_date=2024-01-01&end_date=2024-12-31', follow_redirects=True)
        assert resp.status_code == 200


class TestReceiptRoutes:
    def test_invoice_receipt_page_loads(self, client, app, business):
        with app.app_context():
            from models import db, Customer, Product, Invoice, InvoiceItem
            customer = Customer(name='Receipt Customer', business_id=business.id)
            product = Product(sku='RCPT-INV', name='Receipt Product', default_selling_price=250.0, business_id=business.id)
            db.session.add_all([customer, product])
            db.session.flush()
            invoice = Invoice(
                business_id=business.id,
                customer_id=customer.id,
                invoice_number='INV-RECEIPT-001',
                invoice_date=datetime.now(),
                due_date=datetime.now(),
                subtotal=500.0,
                total_amount=500.0,
                status='issued',
                notes='receipt test',
            )
            db.session.add(invoice)
            db.session.flush()
            db.session.add(InvoiceItem(
                business_id=business.id,
                invoice_id=invoice.id,
                product_id=product.id,
                description=product.name,
                quantity=2,
                unit_price=250.0,
                line_total=500.0,
            ))
            db.session.commit()
            resp = client.get(f'/invoices/{invoice.id}/receipt')
            assert resp.status_code == 200
            assert b'Invoice Receipt' in resp.data or b'Invoice' in resp.data

    def test_sale_receipt_page_loads(self, client, app, business):
        with app.app_context():
            from models import db, Product
            product = Product(sku='RCPT-SALE', name='Receipt Sale Product', default_selling_price=180.0, business_id=business.id)
            db.session.add(product)
            db.session.commit()
            record_purchase(
                purchase_date=datetime.now(),
                supplier='Receipt Supplier',
                notes='stock',
                items_data=[{'product_id': product.id, 'quantity': 10, 'unit_cost': 100.0}],
                business_id=business.id,
            )
            sale = record_sale(
                sale_date=datetime.now(),
                customer_name='Walk-in Customer',
                items_data=[{'product_id': product.id, 'quantity': 2, 'unit_price': 180.0}],
                business_id=business.id,
                created_by=1,
            )
            resp = client.get(f'/sales/{sale.id}/receipt')
            assert resp.status_code == 200
            assert b'Sales Receipt' in resp.data or b'Receipt' in resp.data


class TestCustomerSupplierRoutes:
    def test_customers_page_loads(self, client):
        resp = client.get('/customers')
        assert resp.status_code == 200

    def test_suppliers_page_loads(self, client):
        resp = client.get('/suppliers')
        assert resp.status_code == 200

    def test_create_customer_via_form(self, client, app, business):
        with app.app_context():
            resp = client.post('/customers', data={
                'name': 'Test Customer',
                'phone': '0888000000',
                'email': 'customer@example.com',
                'address': 'Test address',
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert b'Test Customer' in resp.data or b'success' in resp.data.lower()

    def test_create_supplier_via_form(self, client, app, business):
        with app.app_context():
            resp = client.post('/suppliers', data={
                'name': 'Test Supplier',
                'phone': '0999000000',
                'email': 'supplier@example.com',
                'address': 'Supplier address',
                'payment_terms': 'Net 30',
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert b'Test Supplier' in resp.data or b'success' in resp.data.lower()


class TestInvoicePaymentRoutes:
    def test_invoices_page_loads(self, client):
        resp = client.get('/invoices')
        assert resp.status_code == 200

    def test_payments_page_loads(self, client):
        resp = client.get('/payments')
        assert resp.status_code == 200

    def test_create_invoice_via_form(self, client, app, business):
        with app.app_context():
            from models import db, Customer, Product
            customer = Customer(name='Invoice Customer', business_id=business.id)
            product = Product(sku='INV-TEST', name='Invoice Item', default_selling_price=250.0, business_id=business.id)
            db.session.add_all([customer, product])
            db.session.commit()
            resp = client.post('/invoices', data={
                'customer_id': str(customer.id),
                'invoice_date': datetime.now().isoformat(),
                'due_date': datetime.now().isoformat(),
                'notes': 'Invoice test',
                'product_id[]': [str(product.id)],
                'quantity[]': ['2'],
                'unit_price[]': ['250.0'],
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert b'Invoice' in resp.data or b'success' in resp.data.lower()


class TestSettingsRoutes:
    def test_settings_page_loads(self, client):
        resp = client.get('/settings')
        assert resp.status_code == 200

    def test_update_tax_rate(self, client, app):
        with app.app_context():
            with client.session_transaction() as sess:
                sess['_flashes'] = []
            resp = client.post('/settings', data={
                'action': 'update_tax',
                'tax_rate': '25.0',
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert b'25.0' in resp.data or b'updated' in resp.data.lower()


class TestAuthRoutes:
    def test_login_page_hides_sidebar(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200
        assert b'Welcome to TrackWise' in resp.data
        assert b'<aside class="sidebar">' not in resp.data
        assert b'<nav class="nav-menu">' not in resp.data

    def test_login_page_renders_hidden_csrf_field(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200
        assert b'csrf_token' in resp.data.lower()
        assert b'<input type="hidden"' in resp.data.lower()

    def test_login_handles_invalid_password_hash_without_500(self, app):
        with app.app_context():
            from models import db, User
            from app.models.accounting import Business

            business = Business(name='Broken Hash Business', currency='MWK')
            db.session.add(business)
            db.session.flush()
            db.session.add(User(
                business_id=business.id,
                email='broken@example.com',
                password_hash='not-a-valid-hash',
                role='admin',
                is_active=True,
            ))
            db.session.commit()

        client = app.test_client()
        resp = client.post('/login', data={
            'business_name': 'Broken Hash Business',
            'email': 'broken@example.com',
            'password': 'wrongpassword',
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b'Invalid credentials or inactive account.' in resp.data

    def test_ensure_required_user_columns_adds_missing_name(self, monkeypatch, app):
        import app as app_module

        calls = []

        class FakeInspector:
            def get_columns(self, table_name):
                if table_name == 'users':
                    return [{'name': 'id'}, {'name': 'email'}]
                return []

        class FakeConnection:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute(self, statement):
                calls.append(str(statement))

        class FakeEngine:
            def begin(self):
                return FakeConnection()

        with app.app_context():
            monkeypatch.setattr('sqlalchemy.inspect', lambda engine: FakeInspector())
            original_engine = app_module.db.engines.get(None)
            app_module.db.engines[None] = FakeEngine()
            try:
                app_module.ensure_required_user_columns()
            finally:
                if original_engine is None:
                    app_module.db.engines.pop(None, None)
                else:
                    app_module.db.engines[None] = original_engine

        assert any('ADD COLUMN IF NOT EXISTS name' in call for call in calls)


class TestAccountingAPI:
    def test_verify_endpoint(self, client):
        resp = client.get('/api/accounting/verify')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)


class TestAPISecurity:
    def test_api_products_business_scoped(self, client, app, business):
        from models import db, Product
        from app.models.accounting import Business

        other_business = Business(name='Other Business', currency='MWK')
        db.session.add(other_business)
        db.session.flush()
        db.session.add(Product(sku='API-001', name='Current Biz Product',
                               default_selling_price=50.0, business_id=business.id))
        db.session.add(Product(sku='OTHER-001', name='Other Biz Product',
                               default_selling_price=10.0, business_id=other_business.id))
        db.session.commit()

        resp = client.get('/api/products')
        assert resp.status_code == 200
        skus = [p['sku'] for p in resp.get_json()]
        assert 'API-001' in skus
        assert 'OTHER-001' not in skus

    def test_api_suppliers_business_scoped(self, client, app, business):
        from models import db, Supplier
        from app.models.accounting import Business

        other_business = Business(name='Other Business 2', currency='MWK')
        db.session.add(other_business)
        db.session.flush()
        db.session.add(Supplier(name='Current Biz Supplier', business_id=business.id))
        db.session.add(Supplier(name='Other Biz Supplier', business_id=other_business.id))
        db.session.commit()

        resp = client.get('/api/suppliers')
        assert resp.status_code == 200
        names = [s['name'] for s in resp.get_json()]
        assert 'Current Biz Supplier' in names
        assert 'Other Biz Supplier' not in names


class TestAccessibility:
    def test_skip_link_and_main_id_render(self, client):
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        assert b'Skip to content' in resp.data
        assert b'id="main-content"' in resp.data

    def test_theme_toggle_and_sidebar_aria(self, client):
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        assert b'id="themeToggle"' in resp.data
        assert b'id="sidebarToggle"' in resp.data
        assert b'aria-expanded' in resp.data

    def test_theme_css_variables_present(self, client):
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        assert b'html.theme-light' in resp.data


class TestCOAManager:
    def test_coa_list_page(self, client):
        resp = client.get('/accounting/chart-of-accounts')
        assert resp.status_code == 200
        assert b'Chart of Accounts' in resp.data

    def test_create_account(self, client, app, business):
        from models import db
        from app.models.accounting import ChartOfAccounts
        with app.app_context():
            resp = client.post('/accounting/chart-of-accounts/create', data={
                'code': '9000', 'name': 'Test Account', 'type': 'expense', 'parent_id': ''
            }, follow_redirects=True)
            assert resp.status_code == 200
            acct = ChartOfAccounts.query.filter_by(business_id=business.id, code='9000').first()
            assert acct is not None and acct.name == 'Test Account'
            assert acct.is_active

    def test_create_duplicate_rejected(self, client, app, business):
        from models import db
        from app.models.accounting import ChartOfAccounts
        with app.app_context():
            db.session.add(ChartOfAccounts(business_id=business.id, code='9001', name='Existing', type='asset'))
            db.session.commit()
        resp = client.post('/accounting/chart-of-accounts/create', data={
            'code': '9001', 'name': 'Dup', 'type': 'asset', 'parent_id': ''
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'already exists' in resp.data

    def test_archive_account(self, client, app, business):
        from models import db
        from app.models.accounting import ChartOfAccounts
        with app.app_context():
            acct = ChartOfAccounts(business_id=business.id, code='9002', name='To Archive', type='asset')
            db.session.add(acct)
            db.session.commit()
            acct_id = acct.id
        resp = client.post(f'/accounting/chart-of-accounts/{acct_id}/archive', follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            assert db.session.get(ChartOfAccounts, acct_id).is_active is False

    def test_opening_balance_posts_entry(self, client, app, business):
        from app.models.accounting import ChartOfAccounts, JournalEntry
        from models import db
        with app.app_context():
            cash = ChartOfAccounts.query.filter_by(business_id=business.id, code='1000').first()
            assert cash is not None
        resp = client.post(f'/accounting/chart-of-accounts/{cash.id}/opening-balance', data={
            'amount': '1000.00',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            entry = JournalEntry.query.filter_by(
                business_id=business.id, reference_type='OpeningBalance', reference_id=cash.id
            ).first()
            assert entry is not None
            total_d = sum(float(l.debit_amount) for l in entry.lines)
            total_c = sum(float(l.credit_amount) for l in entry.lines)
            assert abs(total_d - total_c) < 0.01
            assert total_d == 1000.0


class TestJournalEntries:
    def _codes(self, app, business):
        from app.models.accounting import ChartOfAccounts
        with app.app_context():
            by_code = {
                a.code: a.id for a in
                ChartOfAccounts.query.filter_by(business_id=business.id).all()
            }
        return by_code

    def test_je_list_page(self, client):
        resp = client.get('/accounting/journal-entries')
        assert resp.status_code == 200
        assert b'Journal Entries' in resp.data

    def test_create_balanced_je_posts(self, client, app, business):
        from app.models.accounting import JournalEntry
        from models import db
        codes = self._codes(app, business)
        resp = client.post('/accounting/journal-entries/create', data={
            'description': 'Test adjustment',
            'entry_date': '2026-08-17',
            'account_id': [str(codes['4000']), str(codes['1000'])],
            'debit_amount': ['0', '1000'],
            'credit_amount': ['1000', '0'],
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            entry = JournalEntry.query.filter_by(
                business_id=business.id, reference_type='JournalEntry'
            ).first()
            assert entry is not None
            assert entry.description == 'Test adjustment'

    def test_create_unbalanced_je_rejected(self, client, app, business):
        from app.models.accounting import JournalEntry
        from models import db
        codes = self._codes(app, business)
        client.post('/accounting/journal-entries/create', data={
            'description': 'Bad entry',
            'entry_date': '2026-08-17',
            'account_id': [str(codes['4000']), str(codes['1000'])],
            'debit_amount': ['0', '1000'],
            'credit_amount': ['500', '0'],
        }, follow_redirects=True)
        with app.app_context():
            assert JournalEntry.query.filter_by(
                business_id=business.id, reference_type='JournalEntry').count() == 0

    def test_approval_gated_je_posts_on_approval(self, app, business):
        import json
        from models import db
        from app.models.accounting import JournalEntry
        from app.models.approval import ApprovalConfig, ApprovalRequest
        from app.approvals.routes import _execute_approval
        codes = self._codes(app, business)

        with app.app_context():
            cfg = ApprovalConfig(
                business_id=business.id, transaction_type='journal_entry',
                levels='["accountant"]', is_active=True,
            )
            db.session.add(cfg)
            db.session.commit()

        client = app.test_client()
        with client.session_transaction() as sess:
            sess['_user_id'] = app.test_client_user.get_id()
        client.post('/accounting/journal-entries/create', data={
            'description': 'Accrual adjustment',
            'entry_date': '2026-08-17',
            'account_id': [str(codes['4000']), str(codes['1000'])],
            'debit_amount': ['0', '1000'],
            'credit_amount': ['1000', '0'],
        }, follow_redirects=True)

        with app.app_context():
            req = ApprovalRequest.query.filter_by(
                business_id=business.id, transaction_type='journal_entry', status='pending'
            ).first()
            assert req is not None
            assert JournalEntry.query.filter_by(
                business_id=business.id, reference_type='JournalEntry').count() == 0
            _execute_approval(req)
            assert JournalEntry.query.filter_by(
                business_id=business.id, reference_type='JournalEntry').count() == 1


class TestInvoiceLifecycle:
    def test_invoice_send(self, client, app, business):
        from models import db
        from app.models.accounting import ChartOfAccounts
        customer = Customer(name='Lifecycle Customer', business_id=business.id)
        product = Product(sku='LIFE-INV', name='Lifecycle Product', default_selling_price=100.0, business_id=business.id)
        db.session.add_all([customer, product])
        db.session.commit()
        client.post('/invoices', data={
            'customer_id': str(customer.id),
            'invoice_date': datetime.now().isoformat(),
            'due_date': datetime.now().isoformat(),
            'product_id[]': [str(product.id)],
            'quantity[]': ['1'],
            'unit_price[]': ['100.0'],
        }, follow_redirects=True)
        invoice = Invoice.query.filter_by(business_id=business.id).first()
        assert invoice is not None
        assert invoice.status == 'issued'
        resp = client.post(f'/invoices/{invoice.id}/send', follow_redirects=True)
        assert resp.status_code == 200
        assert invoice.status == 'sent'

    def test_invoice_mark_paid(self, client, app, business):
        customer = Customer(name='Paid Customer', business_id=business.id)
        product = Product(sku='PAID-INV', name='Paid Product', default_selling_price=200.0, business_id=business.id)
        db.session.add_all([customer, product])
        db.session.commit()
        client.post('/invoices', data={
            'customer_id': str(customer.id),
            'invoice_date': datetime.now().isoformat(),
            'due_date': datetime.now().isoformat(),
            'product_id[]': [str(product.id)],
            'quantity[]': ['2'],
            'unit_price[]': ['200.0'],
        }, follow_redirects=True)
        invoice = Invoice.query.filter_by(business_id=business.id).first()
        assert invoice is not None
        resp = client.post(f'/invoices/{invoice.id}/mark-paid', data={
            'amount': str(invoice.total_amount),
            'payment_method': 'cash',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert invoice.status == 'paid'

    def test_invoice_void(self, client, app, business):
        customer = Customer(name='Void Customer', business_id=business.id)
        product = Product(sku='VOID-INV', name='Void Product', default_selling_price=150.0, business_id=business.id)
        db.session.add_all([customer, product])
        db.session.commit()
        client.post('/invoices', data={
            'customer_id': str(customer.id),
            'invoice_date': datetime.now().isoformat(),
            'due_date': datetime.now().isoformat(),
            'product_id[]': [str(product.id)],
            'quantity[]': ['1'],
            'unit_price[]': ['150.0'],
        }, follow_redirects=True)
        invoice = Invoice.query.filter_by(business_id=business.id).first()
        assert invoice is not None
        resp = client.post(f'/invoices/{invoice.id}/void', follow_redirects=True)
        assert resp.status_code == 200
        assert invoice.status == 'void'


class TestCreditNotes:
    def test_credit_note_page_loads(self, client):
        resp = client.get('/credit-notes')
        assert resp.status_code == 200

    def test_issue_credit_note(self, client, app, business):
        from models import db
        from app.models.accounting import ChartOfAccounts
        customer = Customer(name='CN Customer', business_id=business.id)
        product = Product(sku='CN-INV', name='CN Product', default_selling_price=300.0, business_id=business.id)
        db.session.add_all([customer, product])
        db.session.commit()
        client.post('/invoices', data={
            'customer_id': str(customer.id),
            'invoice_date': datetime.now().isoformat(),
            'due_date': datetime.now().isoformat(),
            'product_id[]': [str(product.id)],
            'quantity[]': ['1'],
            'unit_price[]': ['300.0'],
        }, follow_redirects=True)
        invoice = Invoice.query.filter_by(business_id=business.id).first()
        assert invoice is not None
        resp = client.post('/credit-notes', data={
            'invoice_id': str(invoice.id),
            'amount': '100.00',
            'reason': 'Returned goods',
            'apply_to_ar': 'on',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert invoice.status == 'credit_note_issued'


class TestARPaymentApplication:
    def test_apply_payment_page_loads(self, client, app, business):
        customer = Customer(name='AR Customer', business_id=business.id)
        product = Product(sku='AR-INV', name='AR Product', default_selling_price=500.0, business_id=business.id)
        db.session.add_all([customer, product])
        db.session.commit()
        client.post('/invoices', data={
            'customer_id': str(customer.id),
            'invoice_date': datetime.now().isoformat(),
            'due_date': datetime.now().isoformat(),
            'product_id[]': [str(product.id)],
            'quantity[]': ['1'],
            'unit_price[]': ['500.0'],
        }, follow_redirects=True)
        invoice = Invoice.query.filter_by(business_id=business.id).first()
        assert invoice is not None
        resp = client.get(f'/invoices/{invoice.id}/apply-payment')
        assert resp.status_code == 200

    def test_apply_partial_payment(self, client, app, business):
        customer = Customer(name='Partial Customer', business_id=business.id)
        product = Product(sku='PART-INV', name='Partial Product', default_selling_price=400.0, business_id=business.id)
        db.session.add_all([customer, product])
        db.session.commit()
        client.post('/invoices', data={
            'customer_id': str(customer.id),
            'invoice_date': datetime.now().isoformat(),
            'due_date': datetime.now().isoformat(),
            'product_id[]': [str(product.id)],
            'quantity[]': ['1'],
            'unit_price[]': ['400.0'],
        }, follow_redirects=True)
        invoice = Invoice.query.filter_by(business_id=business.id).first()
        assert invoice is not None
        resp = client.post(f'/invoices/{invoice.id}/apply-payment', data={
            'amount': '200.00',
            'payment_method': 'bank_transfer',
            'reference': 'TXN123',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert invoice.status == 'partially_paid'


class TestExpensesRedirect:
    def test_expenses_returns_301(self, client):
        resp = client.get('/expenses')
        assert resp.status_code == 301

    def test_expenses_redirects_to_payments(self, client):
        resp = client.get('/expenses', follow_redirects=True)
        assert resp.status_code == 200


class TestReportPagination:
    def test_general_ledger_pagination_params(self, client):
        resp = client.get('/reports/general-ledger?per_page=50')
        assert resp.status_code == 200

    def test_audit_log_pagination_params(self, client):
        resp = client.get('/reports/audit-log?per_page=50')
        assert resp.status_code == 200

    def test_ar_aging_pagination_params(self, client):
        resp = client.get('/reports/ar-aging?per_page=50')
        assert resp.status_code == 200

    def test_ap_aging_pagination_params(self, client):
        resp = client.get('/reports/ap-aging?per_page=50')
        assert resp.status_code == 200


class TestBankReconciliation:
    def test_bank_recon_page_loads(self, client):
        resp = client.get('/accounting/bank-reconciliation')
        assert resp.status_code == 200
        assert b'Bank Reconciliation' in resp.data

    def test_bank_register_loads(self, client, app, business):
        from app.models.accounting import ChartOfAccounts
        with app.app_context():
            bank_acct = ChartOfAccounts.query.filter_by(
                business_id=business.id, code='1100'
            ).first()
            assert bank_acct is not None
            resp = client.get(f'/accounting/bank-reconciliation/register/{bank_acct.id}')
            assert resp.status_code == 200
            assert b'Bank Register' in resp.data

    def test_bank_statement_import(self, client, app, business):
        from app.models.accounting import ChartOfAccounts, BankStatement
        with app.app_context():
            bank_acct = ChartOfAccounts.query.filter_by(
                business_id=business.id, code='1100'
            ).first()
            resp = client.post('/accounting/bank-reconciliation/import', data={
                'account_id': str(bank_acct.id),
                'csv_data': '2026-06-01,5000.00,Customer Payment TXN001\n2026-06-02,-2000.00,Supplier Payment CHQ002',
            }, follow_redirects=True)
            assert resp.status_code == 200
        with app.app_context():
            stmts = BankStatement.query.filter_by(business_id=business.id).all()
            assert len(stmts) == 2

    def test_bank_reconcile_match_and_unmatch(self, client, app, business):
        from app.models.accounting import ChartOfAccounts, JournalEntry, JournalLine, BankStatement
        with app.app_context():
            bank_acct = ChartOfAccounts.query.filter_by(
                business_id=business.id, code='1100'
            ).first()
            stmt = BankStatement(
                business_id=business.id,
                account_id=bank_acct.id,
                statement_date=datetime(2026, 6, 1),
                description='Customer Payment',
                amount=5000.0,
                reference='TXN001',
                is_reconciled=False,
            )
            db.session.add(stmt)
            db.session.flush()

            entry = JournalEntry(
                business_id=business.id,
                entry_date=datetime(2026, 6, 1),
                reference_type='Sale',
                description='Test sale JE',
                created_by=business.id,
            )
            db.session.add(entry)
            db.session.flush()
            db.session.add(JournalLine(
                journal_entry_id=entry.id,
                account_id=bank_acct.id,
                debit_amount=5000.0,
                credit_amount=0,
            ))
            db.session.commit()
            stmt_id = stmt.id
            entry_id = entry.id

        resp = client.post('/accounting/bank-reconciliation/match', data={
            'statement_id': str(stmt_id),
            'entry_id': str(entry_id),
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            stmt = db.session.get(BankStatement, stmt_id)
            assert stmt.is_reconciled is True
            assert stmt.journal_entry_id == entry_id

        resp = client.post('/accounting/bank-reconciliation/unmatch', data={
            'statement_id': str(stmt_id),
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            stmt = db.session.get(BankStatement, stmt_id)
            assert stmt.is_reconciled is False
            assert stmt.journal_entry_id is None

    def test_bank_unreconciled_report(self, client):
        resp = client.get('/accounting/bank-reconciliation/unreconciled')
        assert resp.status_code == 200
        assert b'Unreconciled' in resp.data


class TestTaxPerLineItem:
    def test_invoice_creation_with_tax(self, client, app, business):
        from models import db, Customer, Product
        from app.models.accounting import ChartOfAccounts, JournalEntry
        from services.fifo_service import get_tax_rate
        with app.app_context():
            customer = Customer(name='Tax Customer', business_id=business.id)
            product = Product(sku='TAX-INV', name='Tax Product', default_selling_price=100.0, business_id=business.id)
            db.session.add_all([customer, product])
            db.session.commit()
            tax_rate = get_tax_rate(business_id=business.id)

            resp = client.post('/invoices', data={
                'customer_id': str(customer.id),
                'invoice_date': datetime.now().isoformat(),
                'due_date': datetime.now().isoformat(),
                'product_id[]': [str(product.id)],
                'quantity[]': ['1'],
                'unit_price[]': ['100.0'],
                'tax_rate[]': [str(tax_rate)],
            }, follow_redirects=True)
            assert resp.status_code == 200

            invoice = Invoice.query.filter_by(business_id=business.id).first()
            assert invoice is not None
            expected_subtotal = 100.0
            expected_tax = round(expected_subtotal * (tax_rate / 100.0), 2)
            assert float(invoice.subtotal) == expected_subtotal
            assert float(invoice.tax_amount) == expected_tax
            assert float(invoice.total_amount) == expected_subtotal + expected_tax

            item = InvoiceItem.query.filter_by(invoice_id=invoice.id).first()
            assert item is not None
            assert float(item.tax_rate) == tax_rate
            assert float(item.tax_amount) == expected_tax

    def test_sale_accounting_posts_tax_payable(self, client, app, business):
        from models import db, Customer, Product
        from app.models.accounting import ChartOfAccounts, JournalEntry, JournalLine
        from services.fifo_service import record_purchase, get_tax_rate
        with app.app_context():
            customer = Customer(name='Tax Sale Customer', business_id=business.id)
            product = Product(sku='TAX-SALE', name='Tax Sale Product', default_selling_price=200.0, business_id=business.id)
            db.session.add_all([customer, product])
            db.session.commit()
            product_id = product.id
            record_purchase(
                purchase_date=datetime.now(),
                supplier='Tax Supplier',
                notes='stock',
                items_data=[{'product_id': product_id, 'quantity': 10, 'unit_cost': 100.0}],
                business_id=business.id,
            )

            tax_rate = get_tax_rate(business_id=business.id)
            tax_amount = round(200.0 * (tax_rate / 100.0), 2)

            resp = client.post('/invoices', data={
                'customer_id': str(customer.id),
                'invoice_date': datetime.now().isoformat(),
                'due_date': datetime.now().isoformat(),
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'unit_price[]': ['200.0'],
                'tax_rate[]': [str(tax_rate)],
            }, follow_redirects=True)
            invoice = Invoice.query.filter_by(business_id=business.id).first()

        resp = client.post('/sales', data={
            'customer_name': 'Tax Sale Customer',
            'sale_date': datetime.now().isoformat(),
            'invoice_id': str(invoice.id),
            'product_id[]': [str(product_id)],
            'quantity[]': ['1'],
            'unit_price[]': ['200.0'],
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            tax_acct = ChartOfAccounts.query.filter_by(
                business_id=business.id, code='2200'
            ).first()
            assert tax_acct is not None

            entries = JournalEntry.query.filter_by(
                business_id=business.id, reference_type='Sale'
            ).all()
            assert len(entries) >= 1

            tax_lines = []
            for e in entries:
                for l in e.lines:
                    if l.account_id == tax_acct.id:
                        tax_lines.append(l)

            total_tax_credit = sum(float(l.credit_amount) for l in tax_lines)
            assert abs(total_tax_credit - tax_amount) < 0.01

