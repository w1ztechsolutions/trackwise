import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from models import db, Product, StockTransaction, Purchase, PurchaseItem, Sale, SaleItem, Expense, Setting
from services.fifo_service import (
    record_purchase, record_sale, record_expense,
    get_profit_loss, get_inventory_valuation, get_tax_rate, set_tax_rate,
    InventoryException
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'trackwise_super_secret_key_12345'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'trackwise.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ensure instance folder exists
os.makedirs(app.instance_path, exist_ok=True)

# Initialize database
db.init_app(app)

# Helper function to format currency
@app.template_filter('currency')
def format_currency(value):
    try:
        return f"MWK {float(value):,.2f}"
    except (ValueError, TypeError):
        return f"MWK 0.00"

# Helper function to format dates
@app.template_filter('datetime')
def format_datetime(value, format="%Y-%m-%d %H:%M"):
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime(format)

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    # Fetch high-level P&L details
    # By default, show this month's stats
    today = datetime.now()
    start_of_month = datetime(today.year, today.month, 1)
    # Next month start
    if today.month == 12:
        end_of_month = datetime(today.year + 1, 1, 1)
    else:
        end_of_month = datetime(today.year, today.month + 1, 1)
    
    pl_stats = get_profit_loss() # All-time stats for the dashboard overview
    month_stats = get_profit_loss(start_date=start_of_month, end_date=end_of_month)
    val_stats = get_inventory_valuation()
    
    # Low stock alerts
    low_stock_products = Product.query.filter(Product.quantity_in_stock <= Product.low_stock_threshold).all()
    
    # Recent activity lists
    recent_sales = Sale.query.order_by(Sale.sale_date.desc()).limit(5).all()
    recent_purchases = Purchase.query.order_by(Purchase.purchase_date.desc()).limit(5).all()
    recent_expenses = Expense.query.order_by(Expense.expense_date.desc()).limit(5).all()
    
    # Chart data - Sales vs Expenses for the last 6 months
    chart_labels = []
    chart_sales = []
    chart_expenses = []
    
    for i in range(5, -1, -1):
        # Calculate month
        m_date = today - timedelta(days=i*30) # rough estimate for months
        m_start = datetime(m_date.year, m_date.month, 1)
        if m_date.month == 12:
            m_end = datetime(m_date.year + 1, 1, 1)
        else:
            m_end = datetime(m_date.year, m_date.month + 1, 1)
            
        m_pl = get_profit_loss(start_date=m_start, end_date=m_end)
        chart_labels.append(m_start.strftime("%b %Y"))
        chart_sales.append(m_pl['total_sales'])
        chart_expenses.append(m_pl['total_expenses'])
        
    return render_template(
        'dashboard.html',
        pl=pl_stats,
        month_pl=month_stats,
        valuation=val_stats['total_valuation'],
        low_stock=low_stock_products,
        recent_sales=recent_sales,
        recent_purchases=recent_purchases,
        recent_expenses=recent_expenses,
        chart_labels=chart_labels,
        chart_sales=chart_sales,
        chart_expenses=chart_expenses
    )

@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    if request.method == 'POST':
        sku = request.form.get('sku').strip().upper()
        name = request.form.get('name').strip()
        description = request.form.get('description', '').strip()
        threshold = int(request.form.get('low_stock_threshold', 5))
        selling_price = float(request.form.get('default_selling_price', 0.0))
        
        if not sku or not name:
            flash('SKU and Product Name are required!', 'danger')
            return redirect(url_for('inventory'))
            
        # Check unique SKU
        existing = Product.query.filter_by(sku=sku).first()
        if existing:
            flash(f'Product with SKU {sku} already exists!', 'danger')
            return redirect(url_for('inventory'))
            
        product = Product(
            sku=sku,
            name=name,
            description=description,
            low_stock_threshold=threshold,
            default_selling_price=selling_price
        )
        db.session.add(product)
        db.session.commit()
        flash(f'Product "{name}" added successfully!', 'success')
        return redirect(url_for('inventory'))
        
    products = Product.query.order_by(Product.name.asc()).all()
    low_stock_count = sum(1 for p in products if p.quantity_in_stock <= p.low_stock_threshold)
    # Fetch inventory valuations
    valuations = get_inventory_valuation()
    val_map = {item['product'].id: item['valuation'] for item in valuations['product_valuations']}
    
    return render_template(
        'inventory.html',
        products=products,
        valuations=val_map,
        total_valuation=valuations['total_valuation'],
        low_stock_count=low_stock_count
    )

@app.route('/api/products')
def api_products():
    products = Product.query.order_by(Product.name.asc()).all()
    return jsonify([p.to_dict() for p in products])

@app.route('/purchases', methods=['GET', 'POST'])
def purchases():
    if request.method == 'POST':
        supplier = request.form.get('supplier').strip()
        notes = request.form.get('notes', '').strip()
        purchase_date_str = request.form.get('purchase_date')
        
        purchase_date = None
        if purchase_date_str:
            purchase_date = datetime.fromisoformat(purchase_date_str)
            
        # Parse product rows from form
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_costs = request.form.getlist('unit_cost[]')
        
        items_data = []
        for i in range(len(product_ids)):
            if not product_ids[i] or not quantities[i] or not unit_costs[i]:
                continue
            items_data.append({
                'product_id': int(product_ids[i]),
                'quantity': int(quantities[i]),
                'unit_cost': float(unit_costs[i])
            })
            
        if not items_data:
            flash('You must add at least one item to record a purchase.', 'danger')
            return redirect(url_for('purchases'))
            
        try:
            record_purchase(purchase_date, supplier, notes, items_data)
            flash('Inventory purchase recorded successfully and stock updated!', 'success')
        except Exception as e:
            flash(f'Error recording purchase: {str(e)}', 'danger')
            
        return redirect(url_for('purchases'))
        
    products = Product.query.order_by(Product.name.asc()).all()
    purchase_records = Purchase.query.order_by(Purchase.purchase_date.desc()).all()
    return render_template('purchases.html', products=products, purchases=purchase_records)

@app.route('/sales', methods=['GET', 'POST'])
def sales():
    if request.method == 'POST':
        customer = request.form.get('customer_name').strip()
        sale_date_str = request.form.get('sale_date')
        
        sale_date = None
        if sale_date_str:
            sale_date = datetime.fromisoformat(sale_date_str)
            
        # Parse product rows from form
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        
        items_data = []
        for i in range(len(product_ids)):
            if not product_ids[i] or not quantities[i] or not unit_prices[i]:
                continue
            items_data.append({
                'product_id': int(product_ids[i]),
                'quantity': int(quantities[i]),
                'unit_price': float(unit_prices[i])
            })
            
        if not items_data:
            flash('You must add at least one item to record a sale.', 'danger')
            return redirect(url_for('sales'))
            
        try:
            record_sale(sale_date, customer, items_data)
            flash('Sale recorded successfully! Stock and COGS calculations updated.', 'success')
        except InventoryException as ie:
            flash(f'Inventory Error: {str(ie)}', 'danger')
        except Exception as e:
            flash(f'Error recording sale: {str(e)}', 'danger')
            
        return redirect(url_for('sales'))
        
    products = Product.query.filter(Product.quantity_in_stock > 0).order_by(Product.name.asc()).all()
    sale_records = Sale.query.order_by(Sale.sale_date.desc()).all()
    return render_template('sales.html', products=products, sales=sale_records)

@app.route('/expenses', methods=['GET', 'POST'])
def expenses():
    if request.method == 'POST':
        category = request.form.get('category').strip()
        description = request.form.get('description', '').strip()
        amount = float(request.form.get('amount', 0.0))
        expense_date_str = request.form.get('expense_date')
        
        expense_date = None
        if expense_date_str:
            expense_date = datetime.fromisoformat(expense_date_str)
            
        if not category or amount <= 0:
            flash('Category and positive Amount are required!', 'danger')
            return redirect(url_for('expenses'))
            
        try:
            record_expense(expense_date, category, description, amount)
            flash('Operating expense recorded successfully!', 'success')
        except Exception as e:
            flash(f'Error recording expense: {str(e)}', 'danger')
            
        return redirect(url_for('expenses'))
        
    expense_records = Expense.query.order_by(Expense.expense_date.desc()).all()
    # Default categories list
    categories = ['Rent', 'Utilities', 'Salaries', 'Marketing', 'Logistics', 'Tax', 'Supplies', 'Other']
    return render_template('expenses.html', expenses=expense_records, categories=categories)

@app.route('/reports')
def reports():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    start_date = None
    end_date = None
    
    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    if end_date_str:
        # Include the entire end day
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
        
    pl_data = get_profit_loss(start_date, end_date)
    valuation_data = get_inventory_valuation()
    
    # Prepare charts data
    expense_cats = list(pl_data['expense_by_category'].keys())
    expense_vals = list(pl_data['expense_by_category'].values())
    
    return render_template(
        'reports.html',
        pl=pl_data,
        total_valuation=valuation_data['total_valuation'],
        start_date=start_date_str,
        end_date=end_date_str,
        expense_cats=expense_cats,
        expense_vals=expense_vals
    )

@app.route('/settings', methods=['GET', 'POST'])
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
                
        return redirect(url_for('settings'))
        
    tax_rate = get_tax_rate()
    return render_template('settings.html', tax_rate=tax_rate)

def seed_demo_data():
    """Seed sample data to show how the app works."""
    # Delete existing records to prevent clutter/duplicates
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
    
    db.session.add_all([p1, p2, p3, p4])
    db.session.commit()
    
    # Set default tax rate to 20%
    set_tax_rate(20.0)
    
    today = datetime.now()
    
    # 1. Purchases (Stocking up)
    # Batch 1 (5 days ago): Restock soap and sugar at cheaper cost
    p_date1 = today - timedelta(days=5)
    record_purchase(
        purchase_date=p_date1,
        supplier="Mwaza Wholesale Ltd",
        notes="First batch restock",
        items_data=[
            {'product_id': p1.id, 'quantity': 100, 'unit_cost': 900.0}, # Soap at 900 MWK
            {'product_id': p4.id, 'quantity': 150, 'unit_cost': 1400.0} # Sugar at 1400 MWK
        ]
    )
    
    # Batch 2 (3 days ago): Restock tea and coffee
    p_date2 = today - timedelta(days=3)
    record_purchase(
        purchase_date=p_date2,
        supplier="Shirley Highlands Estate",
        notes="Tea and Coffee shipment",
        items_data=[
            {'product_id': p2.id, 'quantity': 50, 'unit_cost': 1800.0}, # Tea at 1800 MWK
            {'product_id': p3.id, 'quantity': 25, 'unit_cost': 5500.0} # Coffee at 5500 MWK
        ]
    )
    
    # Batch 3 (2 days ago): Restock Soap at higher cost (testing FIFO)
    p_date3 = today - timedelta(days=2)
    record_purchase(
        purchase_date=p_date3,
        supplier="Mwaza Wholesale Ltd",
        notes="Soap price increase batch",
        items_data=[
            {'product_id': p1.id, 'quantity': 50, 'unit_cost': 1050.0} # Soap at 1050 MWK
        ]
    )
    
    # 2. Sales (Transactions)
    # Sale 1 (4 days ago): Customer buys soap and sugar
    s_date1 = today - timedelta(days=4)
    record_sale(
        sale_date=s_date1,
        customer_name="Zomba Groceries",
        items_data=[
            {'product_id': p1.id, 'quantity': 30, 'unit_price': 1500.0}, # 30 soap (cogs: 30 * 900 = 27000 MWK)
            {'product_id': p4.id, 'quantity': 50, 'unit_price': 2200.0}  # 50 sugar (cogs: 50 * 1400 = 70000 MWK)
        ]
    )
    
    # Sale 2 (2 days ago): Customer buys coffee, tea and sugar
    s_date2 = today - timedelta(days=2)
    record_sale(
        sale_date=s_date2,
        customer_name="Blantyre Club House",
        items_data=[
            {'product_id': p2.id, 'quantity': 15, 'unit_price': 2800.0}, # 15 tea (cogs: 15 * 1800 = 27000 MWK)
            {'product_id': p3.id, 'quantity': 8, 'unit_price': 8500.0},  # 8 coffee (cogs: 8 * 5500 = 44000 MWK)
            {'product_id': p4.id, 'quantity': 60, 'unit_price': 2200.0}  # 60 sugar (cogs: 60 * 1400 = 84000 MWK)
        ]
    )
    
    # Sale 3 (1 day ago): Customer buys soap (this should cross FIFO layers!)
    # We have: Soap Layer 1 (remaining: 100 - 30 = 70 units @ 900)
    # Let's buy 80 units of soap.
    # It should take 70 units @ 900 (63,000 MWK) + 10 units @ 1050 (10,500 MWK) = 73,500 MWK COGS.
    s_date3 = today - timedelta(days=1)
    record_sale(
        sale_date=s_date3,
        customer_name="Lilongwe Mini-Mart",
        items_data=[
            {'product_id': p1.id, 'quantity': 80, 'unit_price': 1500.0}
        ]
    )
    
    # 3. Expenses
    record_expense(today - timedelta(days=4), "Rent", "Office rent for June", 120000.0)
    record_expense(today - timedelta(days=3), "Utilities", "ESCOM Pre-paid token", 35000.0)
    record_expense(today - timedelta(days=2), "Utilities", "Airtel Office Fiber", 25000.0)
    record_expense(today - timedelta(days=1), "Salaries", "Wages for shop clerk", 80000.0)
    record_expense(today, "Marketing", "Facebook localized advertising", 15000.0)

# Create tables in DB at startup
with app.app_context():
    db.create_all()
    # Check if we have tax_rate setting
    if not Setting.query.filter_by(key='tax_rate').first():
        set_tax_rate(30.0)

if __name__ == '__main__':
    app.run(debug=True)
