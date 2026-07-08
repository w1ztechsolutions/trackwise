import pytest
from datetime import datetime
from models import Product, Sale, Purchase, Expense
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
                'sku': 'TEST-001',
                'name': 'Test Product',
                'description': 'A test product',
                'low_stock_threshold': 5,
                'default_selling_price': 100.0,
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert b'Test Product' in resp.data or b'success' in resp.data.lower()

    def test_duplicate_sku_rejected(self, client, app):
        with app.app_context():
            client.post('/inventory', data={
                'sku': 'DUP-001',
                'name': 'First',
                'description': '',
                'low_stock_threshold': 5,
                'default_selling_price': 100.0,
            })
            resp = client.post('/inventory', data={
                'sku': 'DUP-001',
                'name': 'Second',
                'description': '',
                'low_stock_threshold': 5,
                'default_selling_price': 100.0,
            }, follow_redirects=True)
            assert b'already exists' in resp.data or b'DUP-001' in resp.data

    def test_api_products(self, client, app):
        with app.app_context():
            p = Product(sku='API-001', name='API Product', default_selling_price=50.0)
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

    def test_record_purchase(self, client, app):
        with app.app_context():
            from models import db
            p = Product(sku='PUR-001', name='Purchase Item', default_selling_price=200.0)
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

    def test_record_sale(self, client, app):
        with app.app_context():
            from models import db
            p = Product(sku='SAL-001', name='Sale Item', default_selling_price=300.0)
            db.session.add(p)
            db.session.commit()
            product_id = p.id
            record_purchase(
                purchase_date=datetime.now(),
                supplier='Initial',
                notes='stock',
                items_data=[{'product_id': product_id, 'quantity': 20, 'unit_cost': 100.0}],
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
        resp = client.get('/expenses')
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
        resp = client.get('/reports')
        assert resp.status_code == 200

    def test_reports_with_date_filter(self, client):
        resp = client.get('/reports?start_date=2024-01-01&end_date=2024-12-31')
        assert resp.status_code == 200


class TestCustomerSupplierRoutes:
    def test_customers_page_loads(self, client):
        resp = client.get('/customers')
        assert resp.status_code == 200

    def test_suppliers_page_loads(self, client):
        resp = client.get('/suppliers')
        assert resp.status_code == 200

    def test_create_customer_via_form(self, client, app):
        with app.app_context():
            resp = client.post('/customers', data={
                'name': 'Test Customer',
                'phone': '0888000000',
                'email': 'customer@example.com',
                'address': 'Test address',
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert b'Test Customer' in resp.data or b'success' in resp.data.lower()

    def test_create_supplier_via_form(self, client, app):
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

    def test_create_invoice_via_form(self, client, app):
        with app.app_context():
            from models import db, Customer, Product
            customer = Customer(name='Invoice Customer', business_id=None)
            product = Product(sku='INV-TEST', name='Invoice Item', default_selling_price=250.0)
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
        assert b'nav-menu' not in resp.data


class TestAccountingAPI:
    def test_verify_endpoint_no_auth(self, client):
        resp = client.get('/api/accounting/verify')
        assert resp.status_code == 400
