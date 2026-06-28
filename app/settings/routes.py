from datetime import datetime
from flask_login import login_required
from flask import flash, redirect, render_template, request, url_for

from models import Expense, Product, Purchase, PurchaseItem, Sale, SaleItem, Setting, StockTransaction
from services.fifo_service import record_expense, record_purchase, record_sale, get_tax_rate, set_tax_rate

from . import settings_bp
from app.auth.decorators import role_required


def seed_demo_data():
    """Seed sample data to show how the app works."""
    # Delete existing records to prevent clutter/duplicates
    from models import db

    db.session.query(StockTransaction).delete()
    db.session.query(PurchaseItem).delete()
    db.session.query(Purchase).delete()
    db.session.query(SaleItem).delete()
    db.session.query(Sale).delete()
    db.session.query(Expense).delete()
    db.session.query(Product).delete()
    db.session.commit()

    # Seed Products
    p1 = Product(sku='SOAP-001', name='Malawi Sun Soap', description='Vibrant local moisturizing soap.', low_stock_threshold=10, default_selling_price=1500.0)
    p2 = Product(sku='TEA-002', name='Thyolo Gold Tea (250g)', description='Premium handpicked black tea from Thyolo.', low_stock_threshold=15, default_selling_price=2800.0)
    p3 = Product(sku='COF-003', name='Mzuzu Ground Coffee (500g)', description='Rich aromatic medium-roast coffee.', low_stock_threshold=5, default_selling_price=8500.0)
    p4 = Product(sku='SUG-004', name='Illovo White Sugar (1kg)', description='Fine granulated sugar.', low_stock_threshold=20, default_selling_price=2200.0)

    from models import db

    db.session.add_all([p1, p2, p3, p4])
    db.session.commit()

    set_tax_rate(20.0)

    today = datetime.now()

    from datetime import timedelta

    # Purchases
    p_date1 = today - timedelta(days=5)
    record_purchase(
        purchase_date=p_date1,
        supplier="Mwaza Wholesale Ltd",
        notes="First batch restock",
        items_data=[
            {'product_id': p1.id, 'quantity': 100, 'unit_cost': 900.0},
            {'product_id': p4.id, 'quantity': 150, 'unit_cost': 1400.0}
        ]
    )

    p_date2 = today - timedelta(days=3)
    record_purchase(
        purchase_date=p_date2,
        supplier="Shirley Highlands Estate",
        notes="Tea and Coffee shipment",
        items_data=[
            {'product_id': p2.id, 'quantity': 50, 'unit_cost': 1800.0},
            {'product_id': p3.id, 'quantity': 25, 'unit_cost': 5500.0}
        ]
    )

    p_date3 = today - timedelta(days=2)
    record_purchase(
        purchase_date=p_date3,
        supplier="Mwaza Wholesale Ltd",
        notes="Soap price increase batch",
        items_data=[
            {'product_id': p1.id, 'quantity': 50, 'unit_cost': 1050.0}
        ]
    )

    # Sales
    s_date1 = today - timedelta(days=4)
    record_sale(
        sale_date=s_date1,
        customer_name="Zomba Groceries",
        items_data=[
            {'product_id': p1.id, 'quantity': 30, 'unit_price': 1500.0},
            {'product_id': p4.id, 'quantity': 50, 'unit_price': 2200.0}
        ]
    )

    s_date2 = today - timedelta(days=2)
    record_sale(
        sale_date=s_date2,
        customer_name="Blantyre Club House",
        items_data=[
            {'product_id': p2.id, 'quantity': 15, 'unit_price': 2800.0},
            {'product_id': p3.id, 'quantity': 8, 'unit_price': 8500.0},
            {'product_id': p4.id, 'quantity': 60, 'unit_price': 2200.0}
        ]
    )

    s_date3 = today - timedelta(days=1)
    record_sale(
        sale_date=s_date3,
        customer_name="Lilongwe Mini-Mart",
        items_data=[
            {'product_id': p1.id, 'quantity': 80, 'unit_price': 1500.0}
        ]
    )

    # Expenses
    record_expense(today - timedelta(days=4), "Rent", "Office rent for June", 120000.0)
    record_expense(today - timedelta(days=3), "Utilities", "ESCOM Pre-paid token", 35000.0)
    record_expense(today - timedelta(days=2), "Utilities", "Airtel Office Fiber", 25000.0)
    record_expense(today - timedelta(days=1), "Salaries", "Wages for shop clerk", 80000.0)
    record_expense(today, "Marketing", "Facebook localized advertising", 15000.0)


@settings_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'accountant')
def settings():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_tax':
            rate = float(request.form.get('tax_rate', 30.0))
            if rate < 0 or rate > 100:
                flash('Tax rate must be between 0% and 100%.', 'danger')
            else:
                set_tax_rate(rate)
                flash(f'Tax rate updated to {rate}% successfully!', 'success')

        elif action == 'seed_data':
            try:
                seed_demo_data()
                flash('Demo business and transactions seeded successfully!', 'success')
            except Exception as e:
                flash(f'Error seeding data: {str(e)}', 'danger')

        return redirect(url_for('settings.settings'))

    tax_rate = get_tax_rate()
    return render_template('settings.html', tax_rate=tax_rate)

