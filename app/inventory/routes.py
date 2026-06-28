from flask_login import login_required
from flask import flash, redirect, render_template, request, url_for

from models import Product, Warehouse
from services.fifo_service import get_inventory_valuation
from app.services.inventory_service import (
    adjust_stock,
    transfer_stock,
    InventoryServiceException,
)


from . import inventory_bp


@inventory_bp.route('/inventory', methods=['GET', 'POST'])
@login_required
def inventory():
    if request.method == 'POST':
        action = request.form.get('action', 'create_product')

        if action == 'create_product':
            sku = request.form.get('sku').strip().upper()
            name = request.form.get('name').strip()
            description = request.form.get('description', '').strip()
            threshold = int(request.form.get('low_stock_threshold', 5))
            selling_price = float(request.form.get('default_selling_price', 0.0))

            warehouse_id_raw = request.form.get('warehouse_id', '').strip()
            warehouse_id = int(warehouse_id_raw) if warehouse_id_raw else None

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
                default_selling_price=selling_price,
                warehouse_id=warehouse_id,
                category=request.form.get('category', '').strip() or None,
                unit_of_measure=request.form.get('unit_of_measure', '').strip() or None,
                barcode=request.form.get('barcode', '').strip() or None,
                is_active=True,
            )

            from models import db

            db.session.add(product)
            db.session.commit()
            flash(f'Product "{name}" added successfully!', 'success')
            return redirect(url_for('inventory.inventory'))

        elif action == 'transfer_stock':
            try:
                product_id = int(request.form['product_id'])
                from_warehouse_id = int(request.form['from_warehouse_id'])
                to_warehouse_id = int(request.form['to_warehouse_id'])
                quantity = int(request.form['quantity'])
                notes = request.form.get('notes', '').strip() or None

                sm = transfer_stock(
                    business_id=getattr(getattr(request, 'user', None), 'business_id', None),
                    product_id=product_id,
                    from_warehouse_id=from_warehouse_id,
                    to_warehouse_id=to_warehouse_id,
                    quantity=quantity,
                    created_by=None,
                    notes=notes,
                    reference_type='Transfer',
                    reference_id=None,
                )
                flash('Stock transfer recorded successfully!', 'success')
            except (KeyError, ValueError) as e:
                flash(f'Invalid transfer input: {e}', 'danger')
            except InventoryServiceException as e:
                flash(str(e), 'danger')

            return redirect(url_for('inventory.inventory'))

        elif action == 'adjust_stock':
            try:
                product_id = int(request.form['product_id'])
                warehouse_id = int(request.form['warehouse_id']) if request.form.get('warehouse_id') else None
                adjustment_type = request.form['adjustment_type']
                quantity = int(request.form['quantity'])
                unit_cost_raw = request.form.get('unit_cost', '').strip()
                unit_cost = None if not unit_cost_raw else unit_cost_raw
                notes = request.form.get('notes', '').strip() or None

                adjust_stock(
                    business_id=getattr(getattr(request, 'user', None), 'business_id', None),
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    adjustment_type=adjustment_type,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    created_by=None,
                    notes=notes,
                    reference_type='Adjustment',
                    reference_id=None,
                )
                flash('Stock adjustment recorded successfully!', 'success')
            except (KeyError, ValueError) as e:
                flash(f'Invalid adjustment input: {e}', 'danger')
            except InventoryServiceException as e:
                flash(str(e), 'danger')

            return redirect(url_for('inventory.inventory'))

        else:
            flash('Unknown inventory action.', 'danger')
            return redirect(url_for('inventory.inventory'))

    products = Product.query.order_by(Product.name.asc()).all()
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name.asc()).all()
    low_stock_count = sum(1 for p in products if p.quantity_in_stock <= p.low_stock_threshold)

    valuations = get_inventory_valuation()
    val_map = {item['product'].id: item['valuation'] for item in valuations['product_valuations']}

    return render_template(
        'inventory.html',
        products=products,
        valuations=val_map,
        total_valuation=valuations['total_valuation'],
        low_stock_count=low_stock_count,
        warehouses=warehouses,
    )


@inventory_bp.route('/api/products')
def api_products():
    products = Product.query.order_by(Product.name.asc()).all()
    return [p.to_dict() for p in products], 200



