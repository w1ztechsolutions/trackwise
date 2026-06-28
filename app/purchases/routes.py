from datetime import datetime

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user

from models import Product, Purchase, PurchaseItem
from services.fifo_service import record_purchase

from . import purchases_bp


@purchases_bp.route('/purchases', methods=['GET', 'POST'])
@login_required
def purchases():
    if request.method == 'POST':
        supplier = request.form.get('supplier', '').strip()
        notes = request.form.get('notes', '').strip()
        purchase_date_str = request.form.get('purchase_date')

        purchase_date = None
        if purchase_date_str:
            purchase_date = datetime.fromisoformat(purchase_date_str)

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
            return redirect(url_for('purchases.purchases'))

        try:
            record_purchase(purchase_date, supplier, notes, items_data, current_user.business_id, current_user.id)
            flash('Inventory purchase recorded successfully and stock updated!', 'success')
        except Exception as e:
            flash(f'Error recording purchase: {str(e)}', 'danger')

        return redirect(url_for('purchases.purchases'))

    products = Product.query.order_by(Product.name.asc()).all()
    page = request.args.get('page', 1, type=int)
    purchase_records = Purchase.query.order_by(Purchase.purchase_date.desc()).paginate(page=page, per_page=10)
    return render_template('purchases.html', products=products, purchases=purchase_records)