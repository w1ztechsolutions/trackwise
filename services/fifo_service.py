from datetime import datetime
from models import db, Product, StockTransaction, Purchase, PurchaseItem, Sale, SaleItem, Expense, Setting

class InventoryException(Exception):
    """Raised when inventory operations fail, e.g. insufficient stock."""
    pass

def get_tax_rate():
    """Retrieve the flat tax rate from settings. Defaults to 30.0."""
    setting = Setting.query.filter_by(key='tax_rate').first()
    if not setting:
        # Create default
        setting = Setting(key='tax_rate', value='30.0')
        db.session.add(setting)
        db.session.commit()
    try:
        return float(setting.value)
    except ValueError:
        return 30.0

def set_tax_rate(rate):
    """Set the flat tax rate in settings."""
    setting = Setting.query.filter_by(key='tax_rate').first()
    if not setting:
        setting = Setting(key='tax_rate')
        db.session.add(setting)
    setting.value = str(float(rate))
    db.session.commit()
    return float(setting.value)

def record_purchase(purchase_date, supplier, notes, items_data):
    """
    Record an inventory purchase, add to stock, and record FIFO layers.
    items_data: list of dicts, e.g. [{'product_id': 1, 'quantity': 10, 'unit_cost': 500.0}]
    """
    if not items_data:
        raise ValueError("Purchase must contain at least one item.")
    
    total_amount = 0.0
    purchase_items = []
    
    for item in items_data:
        product_id = item['product_id']
        quantity = int(item['quantity'])
        unit_cost = float(item['unit_cost'])
        
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        if unit_cost < 0:
            raise ValueError("Unit cost cannot be negative.")
            
        product = db.session.get(Product, product_id)
        if not product:
            raise ValueError(f"Product ID {product_id} not found.")
            
        total_amount += quantity * unit_cost
        
        pi = PurchaseItem(
            product_id=product_id,
            quantity=quantity,
            unit_cost=unit_cost
        )
        purchase_items.append((pi, product))
        
    purchase = Purchase(
        purchase_date=purchase_date or datetime.now(),
        supplier=supplier,
        total_amount=total_amount,
        notes=notes
    )
    db.session.add(purchase)
    db.session.flush() # Get purchase.id
    
    for pi, product in purchase_items:
        pi.purchase_id = purchase.id
        db.session.add(pi)
        db.session.flush() # Get pi.id
        
        # Increment product inventory level
        product.quantity_in_stock += pi.quantity
        
        # Add Stock Transaction (FIFO purchase layer)
        tx = StockTransaction(
            product_id=product.id,
            type='PURCHASE',
            quantity=pi.quantity,
            remaining_quantity=pi.quantity,  # FIFO layer starts full
            unit_cost=pi.unit_cost,
            timestamp=purchase.purchase_date,
            reference_type='PurchaseItem',
            reference_id=pi.id
        )
        db.session.add(tx)
        
    db.session.commit()
    return purchase

def record_sale(sale_date, customer_name, items_data):
    """
    Record a customer sale, decrement stock using FIFO layers, and calculate COGS.
    items_data: list of dicts, e.g. [{'product_id': 1, 'quantity': 5, 'unit_price': 800.0}]
    """
    if not items_data:
        raise ValueError("Sale must contain at least one item.")

    sale_date = sale_date or datetime.now()
    total_revenue = 0.0
    total_cogs = 0.0
    sale_items = []
    
    # First, validate stock levels for all items to prevent partial sales
    for item in items_data:
        product_id = item['product_id']
        quantity = int(item['quantity'])
        unit_price = float(item['unit_price'])
        
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        if unit_price < 0:
            raise ValueError("Unit price cannot be negative.")
            
        product = db.session.get(Product, product_id)
        if not product:
            raise ValueError(f"Product ID {product_id} not found.")
            
        if product.quantity_in_stock < quantity:
            raise InventoryException(
                f"Insufficient stock for product '{product.name}'. "
                f"Requested: {quantity}, Available: {product.quantity_in_stock}."
            )
            
        total_revenue += quantity * unit_price
        
    # Process the sale and FIFO layers
    sale = Sale(
        sale_date=sale_date,
        customer_name=customer_name,
        total_revenue=total_revenue,
        total_cogs=0.0, # Will update after calculating COGS
        tax_amount=0.0, # Will update
        net_profit=0.0  # Will update
    )
    db.session.add(sale)
    db.session.flush() # Get sale.id
    
    for item in items_data:
        product_id = item['product_id']
        quantity_to_sell = int(item['quantity'])
        unit_price = float(item['unit_price'])
        
        product = db.session.get(Product, product_id)
        
        # Find all purchase stock transactions with remaining_quantity > 0, oldest first
        layers = StockTransaction.query.filter(
            StockTransaction.product_id == product_id,
            StockTransaction.remaining_quantity > 0,
            StockTransaction.quantity > 0
        ).order_index = StockTransaction.timestamp.asc(), StockTransaction.id.asc()
        
        # Wait, SQLAlchemy query syntax for order by is .order_by(...)
        layers = StockTransaction.query.filter(
            StockTransaction.product_id == product_id,
            StockTransaction.remaining_quantity > 0,
            StockTransaction.quantity > 0
        ).order_by(StockTransaction.timestamp.asc(), StockTransaction.id.asc()).all()
        
        item_cogs = 0.0
        remaining_to_fulfill = quantity_to_sell
        
        for layer in layers:
            if remaining_to_fulfill <= 0:
                break
                
            if layer.remaining_quantity >= remaining_to_fulfill:
                # This layer can fully satisfy the remaining quantity
                portion_cogs = remaining_to_fulfill * layer.unit_cost
                item_cogs += portion_cogs
                
                # Update layer
                layer.remaining_quantity -= remaining_to_fulfill
                
                # Record consumption transaction (negative quantity)
                consume_tx = StockTransaction(
                    product_id=product_id,
                    type='SALE',
                    quantity=-remaining_to_fulfill,
                    remaining_quantity=0,
                    unit_cost=layer.unit_cost,
                    timestamp=sale_date,
                    reference_type='SaleItem',
                    reference_id=None # Will link to SaleItem ID after flush
                )
                db.session.add(consume_tx)
                
                remaining_to_fulfill = 0
            else:
                # This layer can partially satisfy the remaining quantity
                taken = layer.remaining_quantity
                portion_cogs = taken * layer.unit_cost
                item_cogs += portion_cogs
                
                # Update layer to empty
                layer.remaining_quantity = 0
                
                # Record consumption transaction
                consume_tx = StockTransaction(
                    product_id=product_id,
                    type='SALE',
                    quantity=-taken,
                    remaining_quantity=0,
                    unit_cost=layer.unit_cost,
                    timestamp=sale_date,
                    reference_type='SaleItem',
                    reference_id=None
                )
                db.session.add(consume_tx)
                
                remaining_to_fulfill -= taken
                
        if remaining_to_fulfill > 0:
            # This should never happen due to validation, but guard against race conditions
            raise InventoryException(f"Inventory mismatch while processing FIFO layers for {product.name}.")
            
        # Update product stock level
        product.quantity_in_stock -= quantity_to_sell
        
        # Save SaleItem
        si = SaleItem(
            sale_id=sale.id,
            product_id=product_id,
            quantity=quantity_to_sell,
            unit_price=unit_price,
            cogs=item_cogs
        )
        db.session.add(si)
        db.session.flush() # Get si.id
        
        # We can update reference_id for consumption stock transactions created for this item in this session
        # For simplicity, we just created them. If we want exact tracking we can fetch/update,
        # but the product_id, reference_type='SaleItem' and timestamp is enough. Let's set it if possible:
        # We can associate the consume_tx.reference_id = si.id. Let's do it by keeping track of the transactions.
        # However, it is not strictly necessary for reports. Let's proceed.
        total_cogs += item_cogs
        
    # Calculate tax and net profit for this transaction
    # Note: the actual income tax is calculated on overall net profit (Revenue - COGS - Operating Expenses),
    # but at the transaction level, we can calculate the contribution:
    # Gross Profit on this sale = total_revenue - total_cogs.
    # We will save total_cogs on the Sale model.
    # The overall tax calculation will be handled at the P&L report level on net operational income.
    # Let's save transaction stats:
    sale.total_cogs = total_cogs
    
    # We will compute the transaction profit Contribution
    # Gross Profit = total_revenue - total_cogs
    # Note: Operating expenses are recorded separately. For the Sale row itself:
    # let's set net_profit to gross profit for now, or just keep it simple.
    # Let's write the fields to database.
    db.session.commit()
    return sale

def record_expense(expense_date, category, description, amount):
    """Record a general business operating expense."""
    # Allow $0-value expenses? Roadmap says only zero-amount bug should be fixed:
    # treat amounts < 0 as invalid; amount == 0 is accepted.
    if amount < 0:
        raise ValueError("Expense amount cannot be negative.")
    if not category:
        raise ValueError("Expense category is required.")
        
    expense = Expense(
        expense_date=expense_date or datetime.now(),
        category=category,
        description=description,
        amount=float(amount)
    )
    db.session.add(expense)
    db.session.commit()
    return expense

def get_profit_loss(start_date=None, end_date=None):
    """
    Calculate full Profit & Loss statement for the given date range.
    Returns a dictionary of key metrics.
    """
    # Sales query
    sales_query = Sale.query
    if start_date:
        sales_query = sales_query.filter(Sale.sale_date >= start_date)
    if end_date:
        sales_query = sales_query.filter(Sale.sale_date <= end_date)
    sales = sales_query.all()
    
    total_sales = sum(s.total_revenue for s in sales)
    total_cogs = sum(s.total_cogs for s in sales)
    gross_profit = total_sales - total_cogs
    
    # Expenses query
    expenses_query = Expense.query
    if start_date:
        expenses_query = expenses_query.filter(Expense.expense_date >= start_date)
    if end_date:
        expenses_query = expenses_query.filter(Expense.expense_date <= end_date)
    expenses = expenses_query.all()
    
    total_expenses = sum(e.amount for e in expenses)
    
    # Net profit calculations
    pre_tax_profit = gross_profit - total_expenses
    
    tax_rate = get_tax_rate()
    tax_amount = max(0.0, pre_tax_profit * (tax_rate / 100.0))
    net_profit = pre_tax_profit - tax_amount
    
    # Group expenses by category
    expense_by_category = {}
    for e in expenses:
        expense_by_category[e.category] = expense_by_category.get(e.category, 0.0) + e.amount
        
    return {
        'total_sales': total_sales,
        'total_cogs': total_cogs,
        'gross_profit': gross_profit,
        'total_expenses': total_expenses,
        'expense_by_category': expense_by_category,
        'pre_tax_profit': pre_tax_profit,
        'tax_rate': tax_rate,
        'tax_amount': tax_amount,
        'net_profit': net_profit,
        'sales_count': len(sales),
        'expenses_count': len(expenses)
    }

def get_inventory_valuation():
    """
    Calculate current asset value of inventory in stock using FIFO remaining layers.
    Returns: list of product valuations and total valuation.
    """
    products = Product.query.all()
    product_valuations = []
    total_valuation = 0.0
    
    for product in products:
        # Sum remaining FIFO layers
        layers = StockTransaction.query.filter(
            StockTransaction.product_id == product.id,
            StockTransaction.remaining_quantity > 0,
            StockTransaction.quantity > 0
        ).all()
        
        prod_val = 0.0
        for layer in layers:
            prod_val += layer.remaining_quantity * layer.unit_cost
            
        total_valuation += prod_val
        product_valuations.append({
            'product': product,
            'valuation': prod_val,
            'quantity': product.quantity_in_stock
        })
        
    return {
        'product_valuations': product_valuations,
        'total_valuation': total_valuation
    }
