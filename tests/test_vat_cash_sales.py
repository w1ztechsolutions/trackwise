"""Phase B VAT flows: output VAT on walk-in cash sales.

The purchase side (input VAT via Bills, Dr 2200) and the invoice flow were
already wired through the tax engine; these tests cover the remaining gap:
cash checkout sales charging 17.5% standard VAT, posting Cr 2200 with the
cash side debited gross, revenue booked net, and the VAT return netting
output against input.
"""
from datetime import datetime

import pytest

from models import (
    db,
    Product,
    ChartOfAccounts,
    JournalEntry,
    Invoice,
    Customer,
)
from app.services import tax_service
from app.services.fifo_service import record_purchase, record_sale
from app.services.reports.vat_return import get_vat_return


def _seed_product(business_id, cost=100.0, price=200.0, sku='VAT-P', name='Vat Product'):
    product = Product(
        business_id=business_id,
        sku=sku,
        name=name,
        default_selling_price=price,
    )
    db.session.add(product)
    db.session.commit()
    return product


def _vat_standard(business_id):
    """Return the business's VAT-S code id, persisted to the database.

    ensure_default_tax_codes only flushes; committing here keeps the codes
    alive after the surrounding app context tears down (its rollback would
    otherwise wipe them before the route under test runs).
    """
    tax_service.ensure_default_tax_codes(business_id)
    db.session.commit()
    code = next(
        tc for tc in tax_service.list_tax_codes(business_id) if tc.code == 'VAT-S'
    )
    return code.id


def _entry_lines(business_id, reference_type, reference_id):
    entry = JournalEntry.query.filter_by(
        business_id=business_id,
        reference_type=reference_type,
        reference_id=reference_id,
    ).first()
    assert entry is not None
    return entry.lines


class TestCashSaleOutputVat:
    def test_cash_sale_with_standard_vat_posts_gross_cash_and_tax(self, app, business):
        with app.app_context():
            product = _seed_product(business.id, cost=100.0, price=200.0)
            record_purchase(
                purchase_date=datetime(2026, 10, 20),
                supplier='Stock Supplier',
                notes=None,
                items_data=[{'product_id': product.id, 'quantity': 10, 'unit_cost': 100.0}],
                business_id=business.id,
                created_by=None,
            )
            vat_s = _vat_standard(business.id)

            sale = record_sale(
                sale_date=datetime(2026, 10, 20),
                customer_name=None,
                items_data=[{
                    'product_id': product.id,
                    'quantity': 4,
                    'unit_price': 200.0,
                    'tax_code_id': vat_s,
                }],
                business_id=business.id,
                created_by=None,
            )

            # net revenue 800.00, tax 17.5% = 140.00, gross 940.00
            assert float(sale.tax_amount) == pytest.approx(140.00)
            assert float(sale.total_revenue) == pytest.approx(800.00)

            lines = _entry_lines(business.id, 'Sale', sale.id)
            by_code = {}
            for line in lines:
                acct = ChartOfAccounts.query.get(line.account_id)
                by_code.setdefault(acct.code, [0.0, 0.0])
                by_code[acct.code][0] += float(line.debit_amount)
                by_code[acct.code][1] += float(line.credit_amount)

            assert by_code['1000'][0] == pytest.approx(940.00), 'cash debited GROSS'
            assert by_code['4000'][1] == pytest.approx(800.00), 'revenue credited NET'
            assert by_code['2200'][1] == pytest.approx(140.00), 'output VAT to 2200'
            assert by_code['5000'][0] == pytest.approx(400.00), 'COGS from FIFO'
            assert by_code['1400'][1] == pytest.approx(400.00)

            total_debit = sum(v[0] for v in by_code.values())
            total_credit = sum(v[1] for v in by_code.values())
            assert total_debit == pytest.approx(total_credit)

    def test_cash_sale_without_tax_code_is_unchanged(self, app, business):
        with app.app_context():
            product = _seed_product(business.id, sku='NOVAT-P', name='No Vat Product')
            record_purchase(
                purchase_date=datetime(2026, 10, 20),
                supplier='S',
                notes=None,
                items_data=[{'product_id': product.id, 'quantity': 5, 'unit_cost': 50.0}],
                business_id=business.id,
                created_by=None,
            )

            sale = record_sale(
                sale_date=datetime(2026, 10, 20),
                customer_name='Walk-in',
                items_data=[{'product_id': product.id, 'quantity': 1, 'unit_price': 90.0}],
                business_id=business.id,
                created_by=None,
            )

            assert float(sale.tax_amount) == 0.0
            lines = _entry_lines(business.id, 'Sale', sale.id)
            touched_2200 = any(
                ChartOfAccounts.query.get(l.account_id).code == '2200' for l in lines
            )
            assert not touched_2200, 'no tax code selected: no VAT posting'

    def test_zero_rated_code_charges_no_tax(self, app, business):
        with app.app_context():
            product = _seed_product(business.id, sku='ZR-P', name='Zero Rated Product')
            record_purchase(
                purchase_date=datetime(2026, 10, 20),
                supplier='S',
                notes=None,
                items_data=[{'product_id': product.id, 'quantity': 5, 'unit_cost': 50.0}],
                business_id=business.id,
                created_by=None,
            )
            tax_service.ensure_default_tax_codes(business.id)
            zero_code = next(
                tc for tc in tax_service.list_tax_codes(business.id) if tc.code == 'VAT-ZR'
            )

            sale = record_sale(
                sale_date=datetime(2026, 10, 20),
                customer_name='Exporter',
                items_data=[{
                    'product_id': product.id,
                    'quantity': 1,
                    'unit_price': 90.0,
                    'tax_code_id': zero_code.id,
                }],
                business_id=business.id,
                created_by=None,
            )
            assert float(sale.tax_amount) == 0.0

    def test_invoice_linked_sale_still_uses_invoice_tax(self, app, business):
        with app.app_context():
            customer = Customer(name='VAT Cust', business_id=business.id)
            product = _seed_product(business.id, sku='INV-P', name='Invoice Product')
            record_purchase(
                purchase_date=datetime(2026, 10, 20),
                supplier='S',
                notes=None,
                items_data=[{'product_id': product.id, 'quantity': 5, 'unit_cost': 50.0}],
                business_id=business.id,
                created_by=None,
            )
            vat_s = _vat_standard(business.id)

            invoice = Invoice(
                business_id=business.id,
                customer_id=customer.id,
                invoice_number='INV-TEST-1',
                invoice_date=datetime(2026, 10, 20),
                due_date=datetime(2026, 11, 20),
                subtotal=1000.00,
                tax_amount=175.00,
                total_amount=1175.00,
                status='issued',
            )
            db.session.add(customer)
            db.session.add(invoice)
            db.session.commit()

            sale = record_sale(
                sale_date=datetime(2026, 10, 20),
                customer_name=customer.name,
                items_data=[{
                    'product_id': product.id,
                    'quantity': 5,
                    'unit_price': 200.0,
                    'tax_code_id': vat_s,  # must be IGNORED for invoice sales
                }],
                business_id=business.id,
                created_by=None,
                invoice_id=invoice.id,
                tax_amount=175.00,
            )
            assert float(sale.tax_amount) == pytest.approx(175.00), (
                'invoice-linked sales keep the invoice tax, not recomputed tax'
            )


class TestVatReturnNetting:
    def test_vat_return_nets_output_minus_input(self, app, business):
        with app.app_context():
            product = _seed_product(business.id, cost=100.0, price=200.0, sku='RET-P', name='Return Product')
            vat_s = _vat_standard(business.id)

            # input VAT: 10 units @100 net + 17.5% = 175.00 input
            record_purchase(
                purchase_date=datetime(2026, 10, 20),
                supplier='S',
                notes=None,
                items_data=[{
                    'product_id': product.id, 'quantity': 10, 'unit_cost': 100.0,
                    'tax_code_id': vat_s,
                }],
                business_id=business.id,
                created_by=None,
            )
            # output VAT: 4 units @200 net + 17.5% = 140.00 output
            record_sale(
                sale_date=datetime(2026, 10, 21),
                customer_name=None,
                items_data=[{
                    'product_id': product.id, 'quantity': 4, 'unit_price': 200.0,
                    'tax_code_id': vat_s,
                }],
                business_id=business.id,
                created_by=None,
            )

            result = get_vat_return(business.id)
            assert float(result['output_tax']) == pytest.approx(140.00)
            assert float(result['input_tax']) == pytest.approx(175.00)
            assert float(result['net_vat']) == pytest.approx(140.00 - 175.00)


class TestCashSaleRoute:
    def test_cash_checkout_route_applies_tax_code(self, client, app, business):
        with app.app_context():
            product = _seed_product(business.id, sku='ROUTE-P', name='Route Product')
            record_purchase(
                purchase_date=datetime(2026, 10, 20),
                supplier='S',
                notes=None,
                items_data=[{'product_id': product.id, 'quantity': 10, 'unit_cost': 100.0}],
                business_id=business.id,
                created_by=None,
            )
            vat_s = _vat_standard(business.id)
            product_id = product.id

        resp = client.post('/sales', data={
            'sale_date': datetime(2026, 10, 20).isoformat(),
            'product_id[]': [str(product_id)],
            'quantity[]': ['2'],
            'unit_price[]': ['150.0'],
            'tax_code[]': [str(vat_s)],
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            from models import Sale
            sale = Sale.query.filter_by(business_id=business.id).order_by(Sale.id.desc()).first()
            assert sale is not None
            assert float(sale.tax_amount) == pytest.approx(52.50), '150*2 * 17.5%'
            assert float(sale.total_revenue) == pytest.approx(300.00)

    def test_cash_checkout_route_without_tax_unchanged(self, client, app, business):
        with app.app_context():
            product = _seed_product(business.id, sku='ROUTE2-P', name='Route Two')
            record_purchase(
                purchase_date=datetime(2026, 10, 20),
                supplier='S',
                notes=None,
                items_data=[{'product_id': product.id, 'quantity': 10, 'unit_cost': 100.0}],
                business_id=business.id,
                created_by=None,
            )
            product_id = product.id

        resp = client.post('/sales', data={
            'sale_date': datetime(2026, 10, 20).isoformat(),
            'product_id[]': [str(product_id)],
            'quantity[]': ['1'],
            'unit_price[]': ['120.0'],
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            from models import Sale
            sale = Sale.query.filter_by(business_id=business.id).order_by(Sale.id.desc()).first()
            assert float(sale.tax_amount or 0) == 0.0
