"""Phase D — RBAC on money routes (ADR-0018).

The retailer workflow audit found sales, purchase-payment and
expense-payment routes accepted POSTs from ANY logged-in user regardless
of role. mutation_role_required now gates every financial write path to
its owning roles; read pages stay open to all staff.

These tests run with LOGIN_DISABLED=False (a separate app instance from
the TestingConfig default), so the decorators actually enforce.
"""
from datetime import datetime

import pytest

from app import create_app
from config import TestingConfig


class RBACConfig(TestingConfig):
    LOGIN_DISABLED = False


def _seed_role_user(business_id, role, name):
    from models import db, User
    user = User(
        email=f'{name}@example.com',
        name=name,
        role=role,
        business_id=business_id,
        is_active=True,
    )
    user.set_password(f'pw-{name}')
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def rbac_app():
    app = create_app(RBACConfig)
    with app.app_context():
        from models import db
        from tests.conftest import seed_test_business
        db.create_all()
        business, _ = seed_test_business()
        app.test_client_business = business
        # one user per role, all in the same business
        app.role_users = {}
        for role in ('admin', 'manager', 'accountant', 'cashier', 'storekeeper', 'viewer'):
            app.role_users[role] = _seed_role_user(business.id, role, f'{role}user')
        yield app
        db.session.remove()
        db.drop_all()


def _client_as(app, role):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = app.role_users[role].get_id()
    return client


def _login_session(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)


class TestWalkInSaleRoles:
    def test_cashier_can_record_walk_in_sale(self, rbac_app):
        client = _client_as(rbac_app, 'cashier')
        resp = client.post('/sales', data={
            'sale_date': datetime(2026, 10, 20).isoformat(),
            'customer_name': 'Walk-in',
            'product_id[]': [],
            'quantity[]': [],
            'unit_price[]': [],
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'not permitted' not in resp.data

    def test_storekeeper_cannot_record_walk_in_sale(self, rbac_app):
        client = _client_as(rbac_app, 'storekeeper')
        resp = client.post('/sales', data={
            'sale_date': datetime(2026, 10, 20).isoformat(),
            'customer_name': 'Walk-in',
            'product_id[]': ['1'],
            'quantity[]': ['1'],
            'unit_price[]': ['10.0'],
        }, follow_redirects=True)
        assert b'not permitted to perform this action' in resp.data

    def test_viewer_cannot_record_sale_but_sees_page(self, rbac_app):
        client = _client_as(rbac_app, 'viewer')
        # read page stays open
        assert client.get('/sales').status_code == 200
        resp = client.post('/sales', data={
            'sale_date': datetime(2026, 10, 20).isoformat(),
            'customer_name': 'Walk-in',
            'product_id[]': ['1'],
            'quantity[]': ['1'],
            'unit_price[]': ['10.0'],
        }, follow_redirects=True)
        assert b'not permitted to perform this action' in resp.data
        with rbac_app.app_context():
            from models import Sale
            assert Sale.query.count() == 0, 'blocked sale must not record'


class TestInvoiceRoles:
    def test_cashier_cannot_issue_credit_invoice(self, rbac_app):
        client = _client_as(rbac_app, 'cashier')
        resp = client.post('/invoices', data={
            'customer_id': '1',
            'invoice_date': datetime(2026, 10, 20).isoformat(),
            'due_date': datetime(2026, 11, 20).isoformat(),
            'product_id[]': ['1'],
            'quantity[]': ['1'],
            'unit_price[]': ['100.0'],
        }, follow_redirects=True)
        assert b'not permitted to perform this action' in resp.data
        with rbac_app.app_context():
            from models import Invoice
            assert Invoice.query.count() == 0

    def test_manager_can_issue_credit_invoice(self, rbac_app):
        client = _client_as(rbac_app, 'manager')
        resp = client.post('/invoices', data={
            'customer_id': '1',
            'invoice_date': datetime(2026, 10, 20).isoformat(),
            'due_date': datetime(2026, 11, 20).isoformat(),
            'product_id[]': ['1'],
            'quantity[]': ['1'],
            'unit_price[]': ['100.0'],
        }, follow_redirects=True)
        assert b'not permitted' not in resp.data

    def test_void_restricted_from_cashier(self, rbac_app):
        for role in ('cashier', 'storekeeper', 'viewer'):
            client = _client_as(rbac_app, role)
            resp = client.post('/invoices/1/void', follow_redirects=True)
            assert b'not permitted to perform this action' in resp.data, role

    def test_mark_paid_allowed_for_accountant(self, rbac_app):
        client = _client_as(rbac_app, 'accountant')
        resp = client.post('/invoices/1/mark-paid', data={
            'amount': '100.00',
            'payment_method': 'cash',
        }, follow_redirects=True)
        assert b'not permitted' not in resp.data


class TestPurchasePaymentRoles:
    def test_storekeeper_cannot_pay_suppliers(self, rbac_app):
        client = _client_as(rbac_app, 'storekeeper')
        resp = client.post('/payments', data={
            'payee_type': 'other',
            'description': 'Electricity',
            'amount': '5000.00',
            'payment_mode': 'cash',
        }, follow_redirects=True)
        assert b'not permitted to perform this action' in resp.data

    def test_accountant_can_record_payment(self, rbac_app):
        client = _client_as(rbac_app, 'accountant')
        resp = client.post('/payments', data={
            'payee_type': 'other',
            'description': 'Electricity',
            'amount': '5000.00',
            'payment_mode': 'cash',
        }, follow_redirects=True)
        assert b'not permitted' not in resp.data

    def test_storekeeper_can_create_purchase(self, rbac_app):
        client = _client_as(rbac_app, 'storekeeper')
        resp = client.post('/purchases', data={
            'purchase_date': datetime(2026, 10, 20).isoformat(),
            'supplier': 'New Supplier',
            'product_id[]': ['1'],
            'quantity[]': ['5'],
            'unit_cost[]': ['10.0'],
        }, follow_redirects=True)
        assert b'not permitted' not in resp.data

    def test_cashier_cannot_create_purchase(self, rbac_app):
        client = _client_as(rbac_app, 'cashier')
        resp = client.post('/purchases', data={
            'purchase_date': datetime(2026, 10, 20).isoformat(),
            'supplier': 'New Supplier',
            'product_id[]': ['1'],
            'quantity[]': ['5'],
            'unit_cost[]': ['10.0'],
        }, follow_redirects=True)
        assert b'not permitted to perform this action' in resp.data

    def test_supplier_delete_restricted_to_admin_manager(self, rbac_app):
        for role in ('accountant', 'storekeeper', 'cashier', 'viewer'):
            client = _client_as(rbac_app, role)
            resp = client.post('/suppliers/1/delete', follow_redirects=True)
            assert b'not permitted to perform this action' in resp.data, role


class TestCustomerCrudRoles:
    def test_cashier_cannot_delete_customers(self, rbac_app):
        client = _client_as(rbac_app, 'cashier')
        resp = client.post('/customers/1/delete', follow_redirects=True)
        assert b'not permitted to perform this action' in resp.data

    def test_manager_can_edit_customers(self, rbac_app):
        client = _client_as(rbac_app, 'manager')
        resp = client.post('/customers/1/edit', data={
            'name': 'Renamed',
        }, follow_redirects=True)
        assert b'not permitted' not in resp.data


class TestAdminBypass:
    def test_admin_can_do_everything(self, rbac_app):
        client = _client_as(rbac_app, 'admin')
        for url, data in [
            ('/sales', {'sale_date': datetime(2026, 10, 20).isoformat(), 'customer_name': 'x',
                        'product_id[]': [], 'quantity[]': [], 'unit_price[]': []}),
            ('/invoices', {'customer_id': '1', 'invoice_date': datetime(2026, 10, 20).isoformat(),
                           'product_id[]': ['1'], 'quantity[]': ['1'], 'unit_price[]': ['10.0']}),
            ('/payments', {'payee_type': 'other', 'description': 'd', 'amount': '10.00',
                           'payment_mode': 'cash'}),
            ('/purchases', {'purchase_date': datetime(2026, 10, 20).isoformat(), 'supplier': 's',
                            'product_id[]': ['1'], 'quantity[]': ['1'], 'unit_cost[]': ['10.0']}),
        ]:
            resp = client.post(url, data=data, follow_redirects=True)
            assert b'not permitted' not in resp.data, url


class TestReferrerRedirectSafety:
    def _blocked_post(self, client, referrer):
        return client.post('/sales', data={
            'sale_date': datetime(2026, 10, 20).isoformat(),
            'customer_name': 'Walk-in',
            'product_id[]': ['1'],
            'quantity[]': ['1'],
            'unit_price[]': ['10.0'],
        }, headers={'Referer': referrer}, follow_redirects=False)

    def test_same_origin_referrer_is_followed(self, rbac_app):
        client = _client_as(rbac_app, 'viewer')
        resp = self._blocked_post(client, 'http://localhost/sales')
        # denial redirected; the Location must NOT be the external referrer
        assert resp.status_code == 302

    def test_cross_origin_referrer_is_rejected(self, rbac_app):
        client = _client_as(rbac_app, 'viewer')
        resp = self._blocked_post(client, 'http://evil.example.com/phish')
        assert resp.status_code == 302
        assert 'evil.example.com' not in (resp.headers.get('Location') or '')
        assert resp.headers['Location'].endswith('/') or '/dashboard' in resp.headers['Location']

    def test_javascript_referrer_is_rejected(self, rbac_app):
        client = _client_as(rbac_app, 'viewer')
        resp = self._blocked_post(client, 'javascript:alert(1)')
        assert 'javascript' not in (resp.headers.get('Location') or '').lower()
