import os
from datetime import datetime, timedelta
from app import create_app
from models import db, Product, StockTransaction, Purchase, PurchaseItem, Sale, SaleItem, Expense, Setting, User, FinancialCategory, LineItem, Staff
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


def seed_financial_categories(business):
    """Seed financial statement categories and line items."""
    categories_data = [
        {
            'name': 'Cost of Sales',
            'code': 'COS',
            'description': 'Direct costs attributable to the production of goods sold',
            'sort_order': 1,
            'line_items': [
                {'name': 'Raw Materials Purchases', 'code': 'RAW_MAT', 'account_code': '5000', 'sort_order': 1},
                {'name': 'Direct Labor', 'code': 'DIR_LAB', 'account_code': '5000', 'sort_order': 2},
                {'name': 'Freight & Shipping', 'code': 'FREIGHT', 'account_code': '5000', 'sort_order': 3},
                {'name': 'Manufacturing Overhead', 'code': 'MFR_OVH', 'account_code': '5000', 'sort_order': 4},
            ]
        },
        {
            'name': 'Operating Expenses',
            'code': 'OPEX',
            'description': 'Regular operational costs to run the business',
            'sort_order': 2,
            'line_items': [
                {'name': 'Rent & Rates', 'code': 'RENT', 'account_code': '5100', 'sort_order': 1},
                {'name': 'Utilities (Electricity, Water, Internet)', 'code': 'UTIL', 'account_code': '5200', 'sort_order': 2},
                {'name': 'Salaries & Wages', 'code': 'SALARY', 'account_code': '5300', 'sort_order': 3},
                {'name': 'Marketing & Advertising', 'code': 'MARKET', 'account_code': '5400', 'sort_order': 4},
                {'name': 'Logistics & Transport', 'code': 'LOGIST', 'account_code': '5900', 'sort_order': 5},
                {'name': 'Office Supplies', 'code': 'SUPPLY', 'account_code': '5900', 'sort_order': 6},
                {'name': 'Insurance', 'code': 'INSUR', 'account_code': '5900', 'sort_order': 7},
            ]
        },
        {
            'name': 'Administrative Expenses',
            'code': 'ADMIN',
            'description': 'General administrative and office management costs',
            'sort_order': 3,
            'line_items': [
                {'name': 'Professional Fees (Legal, Audit)', 'code': 'PROF_FEE', 'account_code': '5900', 'sort_order': 1},
                {'name': 'Travel & Entertainment', 'code': 'TRAVEL', 'account_code': '5900', 'sort_order': 2},
                {'name': 'Communication (Phone, Internet)', 'code': 'COMMS', 'account_code': '5900', 'sort_order': 3},
                {'name': 'Bank Charges', 'code': 'BANK_CHG', 'account_code': '5900', 'sort_order': 4},
            ]
        },
        {
            'name': 'Selling & Distribution Expenses',
            'code': 'SELL',
            'description': 'Costs directly related to selling products and distribution',
            'sort_order': 4,
            'line_items': [
                {'name': 'Sales Commissions', 'code': 'COMM', 'account_code': '5900', 'sort_order': 1},
                {'name': 'Distribution Costs', 'code': 'DIST', 'account_code': '5900', 'sort_order': 2},
                {'name': 'Promotional Materials', 'code': 'PROMO', 'account_code': '5900', 'sort_order': 3},
            ]
        },
        {
            'name': 'Finance Costs',
            'code': 'FIN',
            'description': 'Interest and other financing expenses',
            'sort_order': 5,
            'line_items': [
                {'name': 'Interest on Loans', 'code': 'INT_LOAN', 'account_code': '5900', 'sort_order': 1},
                {'name': 'Loan Processing Fees', 'code': 'LOAN_FEE', 'account_code': '5900', 'sort_order': 2},
            ]
        },
        {
            'name': 'Other Income',
            'code': 'OTH_INC',
            'description': 'Non-operating income and miscellaneous revenue',
            'sort_order': 6,
            'line_items': [
                {'name': 'Interest Income', 'code': 'INT_INC', 'account_code': '4100', 'sort_order': 1},
                {'name': 'Other Miscellaneous Income', 'code': 'MISC_INC', 'account_code': '4100', 'sort_order': 2},
            ]
        },
        {
            'name': 'Tax',
            'code': 'TAX',
            'description': 'Tax obligations and payments',
            'sort_order': 7,
            'line_items': [
                {'name': 'Income Tax', 'code': 'INC_TAX', 'account_code': '2200', 'sort_order': 1},
                {'name': 'Withholding Tax', 'code': 'WHT', 'account_code': '2200', 'sort_order': 2},
                {'name': 'Other Taxes', 'code': 'OTH_TAX', 'account_code': '2200', 'sort_order': 3},
            ]
        },
    ]

    for cat_data in categories_data:
        existing = FinancialCategory.query.filter_by(business_id=business.id, code=cat_data['code']).first()
        if not existing:
            category = FinancialCategory(
                business_id=business.id,
                name=cat_data['name'],
                code=cat_data['code'],
                description=cat_data['description'],
                sort_order=cat_data['sort_order'],
                is_active=True,
            )
            db.session.add(category)
            db.session.flush()

            for li_data in cat_data['line_items']:
                line_item = LineItem(
                    business_id=business.id,
                    category_id=category.id,
                    name=li_data['name'],
                    code=li_data['code'],
                    account_code=li_data['account_code'],
                    sort_order=li_data['sort_order'],
                    is_active=True,
                )
                db.session.add(line_item)

    db.session.commit()


def seed_staff(business):
    """Seed sample staff records."""
    staff_data = [
        {'name': 'John Banda', 'phone': '+265 999 123 456', 'role': 'Sales Clerk', 'department': 'Sales'},
        {'name': 'Mary Kachale', 'phone': '+265 888 789 012', 'role': 'Cashier', 'department': 'Finance'},
        {'name': 'David Mwale', 'phone': '+265 777 345 678', 'role': 'Driver', 'department': 'Logistics'},
    ]
    for s in staff_data:
        existing = Staff.query.filter_by(business_id=business.id, name=s['name']).first()
        if not existing:
            staff = Staff(
                business_id=business.id,
                staff_id=f"STF-{s['name'][:3].upper()}-{business.id}",
                name=s['name'],
                phone=s['phone'],
                role=s['role'],
                department=s['department'],
                is_active=True,
            )
            db.session.add(staff)
    db.session.commit()


def seed_demo_data():
    """Seed sample data to show how the app works."""
    from models import db as _db

    business = seed_accounting_data()
    seed_financial_categories(business)
    seed_staff(business)

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
    from flask_migrate import upgrade
    app = create_app()
    with app.app_context():
        upgrade()
        seed_demo_data()
        print("Demo data seeded successfully.")
