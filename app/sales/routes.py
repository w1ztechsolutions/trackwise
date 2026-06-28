from datetime import datetime
from flask_login import login_required, current_user
from flask import flash, redirect, render_template, request, url_for

from models import Product, Sale, SaleItem
from services.fifo_service import InventoryException, record_sale

from . import sales_bp


@sales_bp.route('/sales', methods=['GET', 'POST'])
@login_required
def sales():
    if request.method == 'POST':
        customer = request.form.get('customer_name').strip()
        sale_date_str = request.form.get('sale_date')

        sale_date = None
        if sale_date_str:
            sale_date = datetime.fromisoformat(sale_date_str)

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
            return redirect(url_for('sales.sales'))

        try:
            record_sale(sale_date, customer, items_data, current_user.business_id, current_user.id)
            flash('Sale recorded successfully! Stock and COGS calculations updated.', 'success')
        except InventoryException as ie:
            flash(f'Inventory Error: {str(ie)}', 'danger')
        except Exception as e:
            flash(f'Error recording sale: {str(e)}', 'danger')

        return redirect(url_for('sales.sales'))

    products = Product.query.filter(Product.quantity_in_stock > 0).order_by(Product.name.asc()).all()
    page = request.args.get('page', 1, type=int)
    sale_records = Sale.query.order_by(Sale.sale_date.desc()).paginate(page=page, per_page=10)
    return render_template('sales.html', products=products, sales=sale_records)

