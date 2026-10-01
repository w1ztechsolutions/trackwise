from datetime import datetime, timezone

from models import db, Product, StockTransaction, Invoice, Setting
from services.fifo_service import (
    record_purchase, record_sale, record_expense,
    get_profit_loss, get_inventory_valuation, set_tax_rate,
    InventoryException
)


def _set_tax_rate(business):
    """Ensure a default tax rate exists for the seeded business."""
    for setting in Setting.query.filter_by(business_id=business.id).all():
        db.session.delete(setting)
    db.session.commit()
    set_tax_rate(30.0, business_id=business.id)


def test_product_creation(app, business):
    with app.app_context():
        p = Product(sku='PROD001', name='Test Product', default_selling_price=200.0, business_id=business.id)
        db.session.add(p)
        db.session.commit()

        retrieved = Product.query.filter_by(sku='PROD001').first()
        assert retrieved is not None
        assert retrieved.name == 'Test Product'
        assert retrieved.quantity_in_stock == 0


def test_fifo_inventory_and_p_l(app, business):
    with app.app_context():
        _set_tax_rate(business)

        # 1. Create a product
        p = Product(sku='LAP001', name='Laptop', default_selling_price=200.0, business_id=business.id)
        db.session.add(p)
        db.session.commit()

        # 2. Record first purchase: 10 units at MWK 100 each
        record_purchase(
            purchase_date=datetime(2026, 6, 1, 10, 0, 0),
            supplier="Supplier A",
            notes="Initial stock",
            items_data=[{'product_id': p.id, 'quantity': 10, 'unit_cost': 100.0}],
            business_id=business.id,
        )

        # Verify product quantity
        p = db.session.get(Product, p.id)
        assert p.quantity_in_stock == 10

        # Verify FIFO layer is recorded
        tx1 = StockTransaction.query.filter_by(transaction_type='PURCHASE').first()
        assert tx1.remaining_quantity == 10
        assert tx1.unit_cost == 100.0

        # 3. Record second purchase: 10 units at MWK 120 each
        record_purchase(
            purchase_date=datetime(2026, 6, 2, 10, 0, 0),
            supplier="Supplier B",
            notes="Restock batch 2",
            items_data=[{'product_id': p.id, 'quantity': 10, 'unit_cost': 120.0}],
            business_id=business.id,
        )

        # Verify product quantity is now 20
        p = db.session.get(Product, p.id)
        assert p.quantity_in_stock == 20

        # Verify database valuation
        val = get_inventory_valuation(business_id=business.id)
        assert val['total_valuation'] == 10 * 100.0 + 10 * 120.0  # 2200.0

        # 4. Record a sale: 12 units at MWK 200 each
        # Under FIFO, this should consume:
        # - 10 units from batch 1 (cost MWK 100 each)
        # - 2 units from batch 2 (cost MWK 120 each)
        # Total COGS should be: 10 * 100 + 2 * 120 = 1240.0
        # Revenue should be: 12 * 200 = 2400.0
        sale = record_sale(
            sale_date=datetime(2026, 6, 3, 15, 0, 0),
            customer_name="Customer X",
            items_data=[{'product_id': p.id, 'quantity': 12, 'unit_price': 200.0}],
            business_id=business.id,
        )

        # Verify product stock level dropped to 8
        p = db.session.get(Product, p.id)
        assert p.quantity_in_stock == 8

        # Verify sale stats
        assert sale.total_revenue == 2400.0
        assert sale.total_cogs == 1240.0

        # Verify FIFO layer remaining quantities
        layers = StockTransaction.query.filter(
            StockTransaction.product_id == p.id,
            StockTransaction.quantity > 0
        ).order_by(StockTransaction.timestamp.asc()).all()

        assert layers[0].remaining_quantity == 0  # first batch completely consumed
        assert layers[1].remaining_quantity == 8  # second batch has 8 units remaining

        # Verify inventory valuation is now: 8 units * MWK 120 = MWK 960.0
        val = get_inventory_valuation(business_id=business.id)
        assert val['total_valuation'] == 960.0

        # 5. Record an operating expense: MWK 160 for internet
        record_expense(
            expense_date=datetime(2026, 6, 4, 10, 0, 0),
            category="Utilities",
            description="Office Internet",
            amount=160.0,
            business_id=business.id,
        )

        # 6. Verify P&L calculations
        # Sales: 2400.0
        # COGS: 1240.0
        # Gross Profit: 1160.0
        # Expenses: 160.0
        # Pre-tax profit: 1000.0
        # Tax (30%): 300.0
        # Net Profit: 700.0
        pl = get_profit_loss(business_id=business.id)
        assert pl['total_sales'] == 2400.0
        assert pl['total_cogs'] == 1240.0
        assert pl['gross_profit'] == 1160.0
        assert pl['total_expenses'] == 160.0
        assert pl['pre_tax_profit'] == 1000.0
        assert pl['tax_rate'] == 30.0
        assert pl['tax_amount'] == 300.0
        assert pl['net_profit'] == 700.0


def test_sales_do_not_auto_create_invoices_and_support_invoice_link(app, business):
    with app.app_context():
        _set_tax_rate(business)

        p = Product(sku='PROD002', name='Tablet', default_selling_price=150.0, business_id=business.id)
        db.session.add(p)
        db.session.commit()

        record_purchase(
            purchase_date=datetime(2026, 6, 1, 9, 0, 0),
            supplier='Supplier A',
            notes='Initial stock',
            items_data=[{'product_id': p.id, 'quantity': 5, 'unit_cost': 60.0}],
            business_id=business.id,
        )

        invoice = Invoice(
            business_id=business.id,
            invoice_number='INV-1001',
            invoice_date=datetime(2026, 6, 3, 12, 0, 0),
            due_date=datetime(2026, 6, 10, 12, 0, 0),
            subtotal=750.0,
            total_amount=750.0,
            status='issued',
            notes='Credit sale invoice',
        )
        db.session.add(invoice)
        db.session.commit()

        sale = record_sale(
            sale_date=datetime(2026, 6, 3, 14, 0, 0),
            customer_name='Credit Customer',
            items_data=[{'product_id': p.id, 'quantity': 2, 'unit_price': 150.0}],
            business_id=business.id,
            invoice_id=invoice.id,
        )

        assert sale.invoice_id == invoice.id
        assert Invoice.query.count() == 1

        cash_sale = record_sale(
            sale_date=datetime(2026, 6, 4, 9, 0, 0),
            customer_name='',
            items_data=[{'product_id': p.id, 'quantity': 1, 'unit_price': 150.0}],
            business_id=business.id,
        )

        assert cash_sale.invoice_id is None
        assert Invoice.query.count() == 1


def test_insufficient_inventory(app, business):
    with app.app_context():
        _set_tax_rate(business)

        p = Product(sku='PROD003', name='Gadget', default_selling_price=100.0, business_id=business.id)
        db.session.add(p)
        db.session.commit()

        # Record 5 items
        record_purchase(
            purchase_date=datetime.now(timezone.utc),
            supplier="Supplier A",
            notes="Refill",
            items_data=[{'product_id': p.id, 'quantity': 5, 'unit_cost': 50.0}],
            business_id=business.id,
        )

        # Try to sell 6 items
        try:
            record_sale(
                sale_date=datetime.now(timezone.utc),
                customer_name="Failing Customer",
                items_data=[{'product_id': p.id, 'quantity': 6, 'unit_price': 100.0}],
                business_id=business.id,
            )
        except InventoryException:
            return
        raise AssertionError('Expected InventoryException for an oversold quantity')
