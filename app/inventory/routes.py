from flask import flash, redirect, render_template, request, url_for

from models import Product
from services.fifo_service import get_inventory_valuation

from . import inventory_bp


@inventory_bp.route('/inventory', methods=['GET', 'POST'])
def inventory():
    if request.method == 'POST':
        sku = request.form.get('sku').strip().upper()
        name = request.form.get('name').strip()
        description = request.form.get('description', '').strip()
        threshold = int(request.form.get('low_stock_threshold', 5))
        selling_price = float(request.form.get('default_selling_price', 0.0))

        if not sku or not name:
            flash('SKU and Product Name are required!', 'danger')
            return redirect(url_for('inventory.inventory'))

        existing = Product.query.filter_by(sku=sku).first()
        if existing:
            flash(f'Product with SKU {sku} already exists!', 'danger')
            return redirect(url_for('inventory.inventory'))

        product = Product(
            sku=sku,
            name=name,
            description=description,
            low_stock_threshold=threshold,
            default_selling_price=selling_price
        )
        from models import db

        db.session.add(product)
        db.session.commit()
        flash(f'Product "{name}" added successfully!', 'success')
        return redirect(url_for('inventory.inventory'))

    products = Product.query.order_by(Product.name.asc()).all()
    low_stock_count = sum(1 for p in products if p.quantity_in_stock <= p.low_stock_threshold)

    valuations = get_inventory_valuation()
    val_map = {item['product'].id: item['valuation'] for item in valuations['product_valuations']}

    return render_template(
        'inventory.html',
        products=products,
        valuations=val_map,
        total_valuation=valuations['total_valuation'],
        low_stock_count=low_stock_count
    )


@inventory_bp.route('/api/products')
def api_products():
    products = Product.query.order_by(Product.name.asc()).all()
    return [p.to_dict() for p in products], 200

