from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import Product, ProductionBatch, MaterialUsage, FinishedGoodOutput, db
from app.services.production_service import (
    ProductionServiceException,
    create_batch,
    consume_material,
    complete_batch,
)

from . import production_bp


@production_bp.route('/production', methods=['GET', 'POST'])
@login_required
def production():
    if request.method == 'POST':
        action = request.form.get('action', 'create_batch')
        if action == 'create_batch':
            try:
                product_id = int(request.form['product_id'])
                quantity = int(request.form['quantity_produced'])
                notes = request.form.get('notes', '').strip() or None
                batch = create_batch(
                    business_id=getattr(current_user, 'business_id', None),
                    product_id=product_id,
                    quantity_produced=quantity,
                    notes=notes,
                    created_by=getattr(current_user, 'id', None),
                )
                flash(f'Production batch {batch.batch_number} created.', 'success')
            except (KeyError, ValueError) as exc:
                flash(f'Invalid batch input: {exc}', 'danger')
            except ProductionServiceException as exc:
                flash(str(exc), 'danger')
            return redirect(url_for('production.production'))

        if action == 'consume_material':
            try:
                batch_id = int(request.form['production_batch_id'])
                product_id = int(request.form['product_id'])
                quantity = int(request.form['quantity'])
                unit_cost = float(request.form.get('unit_cost', 0))
                consume_material(
                    business_id=getattr(current_user, 'business_id', None),
                    production_batch_id=batch_id,
                    product_id=product_id,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    created_by=getattr(current_user, 'id', None),
                )
                flash('Material consumption recorded.', 'success')
            except (KeyError, ValueError) as exc:
                flash(f'Invalid material input: {exc}', 'danger')
            except ProductionServiceException as exc:
                flash(str(exc), 'danger')
            return redirect(url_for('production.production'))

        if action == 'complete_batch':
            try:
                batch_id = int(request.form['production_batch_id'])
                unit_cost = float(request.form.get('unit_cost', 0))
                complete_batch(
                    business_id=getattr(current_user, 'business_id', None),
                    production_batch_id=batch_id,
                    unit_cost=unit_cost,
                    created_by=getattr(current_user, 'id', None),
                )
                flash('Production batch completed.', 'success')
            except (KeyError, ValueError) as exc:
                flash(f'Invalid completion input: {exc}', 'danger')
            except ProductionServiceException as exc:
                flash(str(exc), 'danger')
            return redirect(url_for('production.production'))

    batches = ProductionBatch.query.order_by(ProductionBatch.production_date.desc()).all()
    products = Product.query.order_by(Product.name.asc()).all()
    return render_template('production.html', batches=batches, products=products)


@production_bp.route('/production/<int:batch_id>')
@login_required
def production_detail(batch_id):
    batch = ProductionBatch.query.get_or_404(batch_id)
    return render_template('production_detail.html', batch=batch)
