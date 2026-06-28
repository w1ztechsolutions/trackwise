import os
from datetime import datetime, timedelta
from app import create_app
from models import db, Product, StockTransaction, Purchase, PurchaseItem, Sale, SaleItem, Expense, Setting, User
from services.fifo_service import record_purchase, record_sale, record_expense, set_tax_rate
from app.models.accounting import Business, ChartOfAccounts


def seed_accounting_data():
    """Seed default business and chart of accounts."""
    business = Business.query.first()
    if not business:
        business = Business(
            name='Default Business',
            currency='MWK',
        )
        db.session.add(business)
        db.session.flush()

    default_accounts = [
        ('1000', 'Cash', 'asset'),
        ('1100', 'Bank', 'asset'),
        ('1200', 'Accounts Receivable', 'asset'),
        ('1400', 'Inventory', 'asset'),
        ('1500', 'Fixed Assets', 'asset'),
        ('2100', 'Accounts Payable', 'liability'),
        ('2200', 'Tax Payable', 'liability'),
        ('3000', 'Capital', 'equity'),
        ('3100', 'Retained Earnings', 'equity'),
        ('4000', 'Sales Revenue', 'income'),
        ('4100', 'Other Income', 'income'),
        ('5000', 'Cost of Goods Sold', 'expense'),
        ('5100', 'Rent Expense', 'expense'),
        ('5200', 'Utilities Expense', 'expense'),
        ('5300', 'Salaries Expense', 'expense'),
        ('5400', 'Marketing Expense', 'expense'),
        ('5900', 'Other Expenses', 'expense'),
    ]

    for code, name, type_ in default_accounts:
        existing = ChartOfAccounts.query.filter_by(business_id=business.id, code=code).first()
        if not existing:
            db.session.add(ChartOfAccounts(
                business_id=business.id,
                code=code,
                name=name,
                type=type_,
                is_active=True,
            ))

    db.session.commit()

    users = User.query.all()
    for user in users:
        if user.business_id is None:
            user.business_id = business.id
    db.session.commit()

    return business


def seed_demo_data():
    """Seed sample data to show how the app works."""
    from models import db as _db

    business = seed_accounting_data()

    # Delete existing records to prevent clutter/duplicates
    _db.session.query(StockTransaction).delete()
    _db.session.query(PurchaseItem).delete()
    _db.session.query(Purchase).delete()
    _db.session.query(SaleItem).delete()
    _db.session.query(Sale).delete()
    _db.session.query(Expense).delete()
    _db.session.query(Product).delete()
    _db.session.commit()

    p1 = Product(
        sku='SOAP-001',
        name='Malawi Sun Soap',
        description='Vibrant local moisturizing soap.',
        low_stock_threshold=10,
        default_selling_price=1500.0,
    )
    p2 = Product(
        sku='TEA-002',
        name='Thyolo Gold Tea (250g)',
        description='Premium handpicked black tea from Thyolo.',
        low_stock_threshold=15,
        default_selling_price=2800.0,
    )
    p3 = Product(
        sku='COF-003',
        name='Mzuzu Ground Coffee (500g)',
        description='Rich aromatic medium-roast coffee.',
        low_stock_threshold=5,
        default_selling_price=8500.0,
    )
    p4 = Product(
        sku='SUG-004',
        name='Illovo White Sugar (1kg)',
        description='Fine granulated sugar.',
        low_stock_threshold=20,
        default_selling_price=2200.0,
    )

    _db.session.add_all([p1, p2, p3, p4])
    _db.session.commit()

    set_tax_rate(20.0)

    today = datetime.now()

    p_date1 = today - timedelta(days=5)
    record_purchase(
        purchase_date=p_date1,
        supplier="Mwaza Wholesale Ltd",
        notes="First batch restock",
        items_data=[
            {'product_id': p1.id, 'quantity': 100, 'unit_cost': 900.0},
            {'product_id': p4.id, 'quantity': 150, 'unit_cost': 1400.0},
        ],
        business_id=business.id,
        created_by=business.id,
    )

    p_date2 = today - timedelta(days=3)
    record_purchase(
        purchase_date=p_date2,
        supplier="Shirley Highlands Estate",
        notes="Tea and Coffee shipment",
        items_data=[
            {'product_id': p2.id, 'quantity': 50, 'unit_cost': 1800.0},
            {'product_id': p3.id, 'quantity': 25, 'unit_cost': 5500.0},
        ],
        business_id=business.id,
        created_by=business.id,
    )

    p_date3 = today - timedelta(days=2)
    record_purchase(
        purchase_date=p_date3,
        supplier="Mwaza Wholesale Ltd",
        notes="Soap price increase batch",
        items_data=[
            {'product_id': p1.id, 'quantity': 50, 'unit_cost': 1050.0},
        ],
        business_id=business.id,
        created_by=business.id,
    )

    s_date1 = today - timedelta(days=4)
    record_sale(
        sale_date=s_date1,
        customer_name="Zomba Groceries",
        items_data=[
            {'product_id': p1.id, 'quantity': 30, 'unit_price': 1500.0},
            {'product_id': p4.id, 'quantity': 50, 'unit_price': 2200.0},
        ],
        business_id=business.id,
        created_by=business.id,
    )

    s_date2 = today - timedelta(days=2)
    record_sale(
        sale_date=s_date2,
        customer_name="Blantyre Club House",
        items_data=[
            {'product_id': p2.id, 'quantity': 15, 'unit_price': 2800.0},
            {'product_id': p3.id, 'quantity': 8, 'unit_price': 8500.0},
            {'product_id': p4.id, 'quantity': 60, 'unit_price': 2200.0},
        ],
        business_id=business.id,
        created_by=business.id,
    )

    s_date3 = today - timedelta(days=1)
    record_sale(
        sale_date=s_date3,
        customer_name="Lilongwe Mini-Mart",
        items_data=[
            {'product_id': p1.id, 'quantity': 80, 'unit_price': 1500.0},
        ],
        business_id=business.id,
        created_by=business.id,
    )

    record_expense(today - timedelta(days=4), "Rent", "Office rent for June", 120000.0, business_id=business.id, created_by=business.id)
    record_expense(today - timedelta(days=3), "Utilities", "ESCOM Pre-paid token", 35000.0, business_id=business.id, created_by=business.id)
    record_expense(today - timedelta(days=2), "Utilities", "Airtel Office Fiber", 25000.0, business_id=business.id, created_by=business.id)
    record_expense(today - timedelta(days=1), "Salaries", "Wages for shop clerk", 80000.0, business_id=business.id, created_by=business.id)
    record_expense(today, "Marketing", "Facebook localized advertising", 15000.0, business_id=business.id, created_by=business.id)


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
        seed_demo_data()
        print("Demo data seeded successfully.")
