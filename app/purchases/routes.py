from datetime import datetime, timezone

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user

from models import Product, Purchase, PurchaseItem, Supplier, Payment, db
from services.fifo_service import record_purchase

from . import purchases_bp


@purchases_bp.route('/suppliers', methods=['GET', 'POST'])
@login_required
def suppliers():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Supplier name is required.', 'danger')
            return redirect(url_for('purchases.suppliers'))

        business_id = getattr(current_user, 'business_id', None)
        supplier = Supplier.query.filter_by(business_id=business_id, name=name).first()
        if not supplier:
            supplier = Supplier(business_id=business_id, name=name, is_active=True)
            db.session.add(supplier)
            db.session.commit()
            flash(f'Supplier "{name}" added successfully!', 'success')
        else:
            flash(f'Supplier "{name}" already exists.', 'info')
        return redirect(url_for('purchases.suppliers'))

    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    return render_template('suppliers.html', suppliers=suppliers)


@purchases_bp.route('/payments', methods=['GET', 'POST'])
@login_required
def payments():
    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id', '').strip()
        amount = request.form.get('amount', '').strip()
        reference = request.form.get('reference', '').strip()
        payment_method = request.form.get('payment_method', 'cash').strip()

        if not supplier_id or not amount:
            flash('Supplier and payment amount are required.', 'danger')
            return redirect(url_for('purchases.payments'))

        supplier = db.session.get(Supplier, int(supplier_id))
        if not supplier:
            flash('Selected supplier was not found.', 'danger')
            return redirect(url_for('purchases.payments'))

        payment = Payment(
            business_id=getattr(current_user, 'business_id', None),
            supplier_id=supplier.id,
            payment_date=datetime.now(timezone.utc),
            amount=float(amount),
            payment_method=payment_method or 'cash',
            reference=reference or None,
        )
        db.session.add(payment)
        db.session.commit()
        flash('Payment recorded successfully.', 'success')
        return redirect(url_for('purchases.payments'))

    page = request.args.get('page', 1, type=int)
    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    payments = Payment.query.order_by(Payment.payment_date.desc()).paginate(page=page, per_page=10)
    return render_template('payments.html', suppliers=suppliers, payments=payments)


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