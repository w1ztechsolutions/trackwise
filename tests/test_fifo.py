import unittest
from datetime import datetime, timezone
from flask import Flask
from models import db, Product, StockTransaction, Purchase, Sale, Expense, Setting
from services.fifo_service import (
    record_purchase, record_sale, record_expense,
    get_profit_loss, get_inventory_valuation, set_tax_rate, get_tax_rate,
    InventoryException
)

class TestFIFOService(unittest.TestCase):
    
    def setUp(self):
        # Create an in-memory database Flask application for testing
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(self.app)
        
        # Create tables and load context
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Ensure default tax rate setting exists
        Setting.query.delete()
        db.session.commit()
        set_tax_rate(30.0)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_product_creation(self):
        p = Product(sku='PROD001', name='Test Product', default_selling_price=200.0)
        db.session.add(p)
        db.session.commit()
        
        retrieved = Product.query.filter_by(sku='PROD001').first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, 'Test Product')
        self.assertEqual(retrieved.quantity_in_stock, 0)

    def test_fifo_inventory_and_p_l(self):
        # 1. Create a product
        p = Product(sku='LAP001', name='Laptop', default_selling_price=200.0)
        db.session.add(p)
        db.session.commit()
        
        # 2. Record first purchase: 10 units at MWK 100 each
        record_purchase(
            purchase_date=datetime(2026, 6, 1, 10, 0, 0),
            supplier="Supplier A",
            notes="Initial stock",
            items_data=[{'product_id': p.id, 'quantity': 10, 'unit_cost': 100.0}]
        )
        
        # Verify product quantity
        p = db.session.get(Product, p.id)
        self.assertEqual(p.quantity_in_stock, 10)
        
        # Verify FIFO layer is recorded
        tx1 = StockTransaction.query.filter_by(transaction_type='PURCHASE').first()
        self.assertEqual(tx1.remaining_quantity, 10)
        self.assertEqual(tx1.unit_cost, 100.0)
        
        # 3. Record second purchase: 10 units at MWK 120 each
        record_purchase(
            purchase_date=datetime(2026, 6, 2, 10, 0, 0),
            supplier="Supplier B",
            notes="Restock batch 2",
            items_data=[{'product_id': p.id, 'quantity': 10, 'unit_cost': 120.0}]
        )
        
        # Verify product quantity is now 20
        p = db.session.get(Product, p.id)
        self.assertEqual(p.quantity_in_stock, 20)
        
        # Verify database valuation
        val = get_inventory_valuation()
        self.assertEqual(val['total_valuation'], 10 * 100.0 + 10 * 120.0) # 2200.0
        
        # 4. Record a sale: 12 units at MWK 200 each
        # Under FIFO, this should consume:
        # - 10 units from batch 1 (cost MWK 100 each)
        # - 2 units from batch 2 (cost MWK 120 each)
        # Total COGS should be: 10 * 100 + 2 * 120 = 1240.0
        # Revenue should be: 12 * 200 = 2400.0
        sale = record_sale(
            sale_date=datetime(2026, 6, 3, 15, 0, 0),
            customer_name="Customer X",
            items_data=[{'product_id': p.id, 'quantity': 12, 'unit_price': 200.0}]
        )
        
        # Verify product stock level dropped to 8
        p = db.session.get(Product, p.id)
        self.assertEqual(p.quantity_in_stock, 8)
        
        # Verify sale stats
        self.assertEqual(sale.total_revenue, 2400.0)
        self.assertEqual(sale.total_cogs, 1240.0)
        
        # Verify FIFO layer remaining quantities
        layers = StockTransaction.query.filter(
            StockTransaction.product_id == p.id,
            StockTransaction.quantity > 0
        ).order_by(StockTransaction.timestamp.asc()).all()
        
        self.assertEqual(layers[0].remaining_quantity, 0) # first batch completely consumed
        self.assertEqual(layers[1].remaining_quantity, 8) # second batch has 8 units remaining
        
        # Verify inventory valuation is now: 8 units * MWK 120 = MWK 960.0
        val = get_inventory_valuation()
        self.assertEqual(val['total_valuation'], 960.0)
        
        # 5. Record an operating expense: MWK 160 for internet
        record_expense(
            expense_date=datetime(2026, 6, 4, 10, 0, 0),
            category="Utilities",
            description="Office Internet",
            amount=160.0
        )
        
        # 6. Verify P&L calculations
        # Sales: 2400.0
        # COGS: 1240.0
        # Gross Profit: 1160.0
        # Expenses: 160.0
        # Pre-tax profit: 1000.0
        # Tax (30%): 300.0
        # Net Profit: 700.0
        pl = get_profit_loss()
        self.assertEqual(pl['total_sales'], 2400.0)
        self.assertEqual(pl['total_cogs'], 1240.0)
        self.assertEqual(pl['gross_profit'], 1160.0)
        self.assertEqual(pl['total_expenses'], 160.0)
        self.assertEqual(pl['pre_tax_profit'], 1000.0)
        self.assertEqual(pl['tax_rate'], 30.0)
        self.assertEqual(pl['tax_amount'], 300.0)
        self.assertEqual(pl['net_profit'], 700.0)

    def test_insufficient_inventory(self):
        p = Product(sku='PROD002', name='Gadget', default_selling_price=100.0)
        db.session.add(p)
        db.session.commit()
        
        # Record 5 items
        record_purchase(
            purchase_date=datetime.now(timezone.utc),
            supplier="Supplier A",
            notes="Refill",
            items_data=[{'product_id': p.id, 'quantity': 5, 'unit_cost': 50.0}]
        )
        
        # Try to sell 6 items
        with self.assertRaises(InventoryException):
            record_sale(
                sale_date=datetime.now(timezone.utc),
                customer_name="Failing Customer",
                items_data=[{'product_id': p.id, 'quantity': 6, 'unit_price': 100.0}]
            )

if __name__ == '__main__':
    unittest.main()
