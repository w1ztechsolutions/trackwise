"""Phase C — credit-sale stock reservation (ADR-0017).

Issuing a credit invoice now reserves its lines against on-hand stock:
walk-in sales may only consume the AVAILABLE balance (on hand minus open
invoice lines), while fulfilling an invoice's own reservation checks raw
on-hand. Reservations are DERIVED from invoice lines — no reservation
rows, no migration, and existing open invoices are correct on day one.
"""
from datetime import datetime

import pytest

from models import db, Product, Invoice, InvoiceItem, Customer
from app.services.fifo_service import record_purchase, record_sale, InventoryException
from app.services.inventory_service import (
    InventoryServiceException,
    RESERVED_INVOICE_STATUSES,
    available_quantity,
    ensure_lines_available,
    reserved_quantities,
)


def _seed_stock(business_id, sku, qty, cost=100.0, price=200.0, name='Reserved Product'):
    product = Product(
        business_id=business_id,
        sku=sku,
        name=name,
        default_selling_price=price,
    )
    db.session.add(product)
    db.session.commit()
    record_purchase(
        purchase_date=datetime(2026, 10, 20),
        supplier='Stock Supplier',
        notes=None,
        items_data=[{'product_id': product.id, 'quantity': qty, 'unit_cost': cost}],
        business_id=business_id,
        created_by=None,
    )
    return product


def _open_invoice(business_id, product_id, quantity, unit_price=200.0, status='issued'):
    customer = Customer(name='Credit Cust', business_id=business_id)
    db.session.add(customer)
    db.session.commit()
    invoice = Invoice(
        business_id=business_id,
        customer_id=customer.id,
        invoice_number=f'INV-TEST-{Invoice.query.count() + 1}',
        invoice_date=datetime(2026, 10, 20),
        due_date=datetime(2026, 11, 20),
        subtotal=quantity * unit_price,
        tax_amount=0.0,
        total_amount=quantity * unit_price,
        status=status,
    )
    db.session.add(invoice)
    db.session.flush()
    db.session.add(InvoiceItem(
        business_id=business_id,
        invoice_id=invoice.id,
        product_id=product_id,
        description='Reserved line',
        quantity=quantity,
        unit_price=unit_price,
        line_total=quantity * unit_price,
    ))
    db.session.commit()
    return invoice


class TestReservedQuantities:
    def test_open_invoice_reserves_its_lines(self, app, business):
        with app.app_context():
            product = _seed_stock(business.id, sku='RES-1', qty=10)
            assert reserved_quantities(business.id) == {}

            _open_invoice(business.id, product.id, quantity=4)
            assert reserved_quantities(business.id) == {product.id: 4}
            assert available_quantity(business.id, product.id) == 6

    def test_multiple_open_invoices_aggregate(self, app, business):
        with app.app_context():
            product = _seed_stock(business.id, sku='RES-2', qty=10)
            _open_invoice(business.id, product.id, quantity=4)
            _open_invoice(business.id, product.id, quantity=3)
            assert reserved_quantities(business.id) == {product.id: 7}
            assert available_quantity(business.id, product.id) == 3

    def test_fulfilled_invoice_releases(self, app, business):
        with app.app_context():
            product = _seed_stock(business.id, sku='RES-3', qty=10)
            invoice = _open_invoice(business.id, product.id, quantity=10)

            record_sale(
                sale_date=datetime(2026, 10, 20),
                customer_name='Credit Cust',
                items_data=[{'product_id': product.id, 'quantity': 10, 'unit_price': 200.0}],
                business_id=business.id,
                created_by=None,
                invoice_id=invoice.id,
            )
            assert reserved_quantities(business.id) == {}, 'sale fulfilled the reservation'

    def test_voided_and_paid_invoices_do_not_reserve(self, app, business):
        with app.app_context():
            product = _seed_stock(business.id, sku='RES-4', qty=10)
            _open_invoice(business.id, product.id, quantity=2, status='void')
            _open_invoice(business.id, product.id, quantity=3, status='paid')
            assert reserved_quantities(business.id) == {}
            assert available_quantity(business.id, product.id) == 10

    def test_draft_sent_and_partially_paid_reserve(self, app, business):
        with app.app_context():
            product = _seed_stock(business.id, sku='RES-5', qty=10)
            for status in ('draft', 'sent', 'partially_paid'):
                _open_invoice(business.id, product.id, quantity=1, status=status)
            assert reserved_quantities(business.id) == {product.id: 3}
            assert RESERVED_INVOICE_STATUSES == ('draft', 'issued', 'sent', 'partially_paid')


class TestWalkInSalesRespectReservations:
    def test_walk_in_cannot_sell_reserved_units(self, app, business):
        with app.app_context():
            product = _seed_stock(business.id, sku='RES-6', qty=10)
            _open_invoice(business.id, product.id, quantity=10)

            with pytest.raises(InventoryException) as excinfo:
                record_sale(
                    sale_date=datetime(2026, 10, 20),
                    customer_name='Walk-in',
                    items_data=[{'product_id': product.id, 'quantity': 1, 'unit_price': 200.0}],
                    business_id=business.id,
                    created_by=None,
                )
            assert 'reserved for open invoices' in str(excinfo.value)

    def test_walk_in_can_sell_the_unreserved_balance(self, app, business):
        with app.app_context():
            product = _seed_stock(business.id, sku='RES-7', qty=10)
            _open_invoice(business.id, product.id, quantity=6)

            sale = record_sale(
                sale_date=datetime(2026, 10, 20),
                customer_name='Walk-in',
                items_data=[{'product_id': product.id, 'quantity': 4, 'unit_price': 200.0}],
                business_id=business.id,
                created_by=None,
            )
            assert sale is not None
            assert available_quantity(business.id, product.id) == 0

    def test_invoice_fulfilment_consumes_on_hand_despite_reservation(self, app, business):
        with app.app_context():
            product = _seed_stock(business.id, sku='RES-8', qty=10)
            invoice = _open_invoice(business.id, product.id, quantity=10)

            sale = record_sale(
                sale_date=datetime(2026, 10, 20),
                customer_name='Credit Cust',
                items_data=[{'product_id': product.id, 'quantity': 10, 'unit_price': 200.0}],
                business_id=business.id,
                created_by=None,
                invoice_id=invoice.id,
            )
            assert sale is not None, 'fulfilment of its own reservation is allowed'
            assert int(Product.query.get(product.id).quantity_in_stock) == 0


class TestInvoiceCreationGuard:
    def test_ensure_lines_available_rejects_over_promise(self, app, business):
        with app.app_context():
            product = _seed_stock(business.id, sku='RES-9', qty=10)
            _open_invoice(business.id, product.id, quantity=8)

            with pytest.raises(InventoryServiceException) as excinfo:
                ensure_lines_available(business.id, [
                    {'product_id': product.id, 'quantity': 5},
                ])
            assert 'reserved for open invoices' in str(excinfo.value)

    def test_same_product_lines_are_aggregated(self, app, business):
        with app.app_context():
            product = _seed_stock(business.id, sku='RES-10', qty=10)
            _open_invoice(business.id, product.id, quantity=8)

            with pytest.raises(InventoryServiceException):
                # 3 + 4 = 7 > available 2, though neither line alone is
                # larger than the on-hand total
                ensure_lines_available(business.id, [
                    {'product_id': product.id, 'quantity': 3},
                    {'product_id': product.id, 'quantity': 4},
                ])

    def test_route_rejects_overselling_invoice(self, client, app, business):
        with app.app_context():
            product = _seed_stock(business.id, sku='RES-11', qty=10)
            _open_invoice(business.id, product.id, quantity=10)
            customer = Customer.query.filter_by(business_id=business.id).first()
            customer_id, product_id = customer.id, product.id

        resp = client.post('/invoices', data={
            'customer_id': str(customer_id),
            'invoice_date': datetime(2026, 10, 20).isoformat(),
            'due_date': datetime(2026, 11, 20).isoformat(),
            'product_id[]': [str(product_id)],
            'quantity[]': ['3'],
            'unit_price[]': ['200.0'],
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'reserved for open invoices' in resp.data

        with app.app_context():
            assert Invoice.query.filter_by(business_id=business.id).count() == 1, (
                'rejected invoice must leave no new rows behind'
            )

    def test_api_products_reports_available(self, client, app, business):
        with app.app_context():
            product = _seed_stock(business.id, sku='RES-12', qty=10)
            _open_invoice(business.id, product.id, quantity=4)
            product_id = product.id

        resp = client.get('/api/products')
        assert resp.status_code == 200
        payload = resp.get_json()
        entry = next(p for p in payload if p['id'] == product_id)
        assert entry['reserved_quantity'] == 4
        assert entry['available_quantity'] == 6
        assert entry['quantity_in_stock'] == 10
