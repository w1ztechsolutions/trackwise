from datetime import datetime, timezone
from flask_login import login_required, current_user
from flask import flash, redirect, render_template, request, url_for

from models import Product, Sale, SaleItem, Customer, Invoice, InvoiceItem, Receipt, db
from services.fifo_service import InventoryException, record_sale

from . import sales_bp


@sales_bp.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Customer name is required.', 'danger')
            return redirect(url_for('sales.customers'))

        business_id = getattr(current_user, 'business_id', None)
        customer = Customer.query.filter_by(business_id=business_id, name=name).first()
        if not customer:
            customer = Customer(business_id=business_id, name=name, is_active=True)
            db.session.add(customer)
            db.session.commit()
            flash(f'Customer "{name}" added successfully!', 'success')
        else:
            flash(f'Customer "{name}" already exists.', 'info')
        return redirect(url_for('sales.customers'))

    customers = Customer.query.order_by(Customer.name.asc()).all()
    return render_template('customers.html', customers=customers)


@sales_bp.route('/invoices', methods=['GET', 'POST'])
@login_required
def invoices():
    if request.method == 'POST':
        customer_id = request.form.get('customer_id', '').strip()
        notes = request.form.get('notes', '').strip()
        invoice_date_str = request.form.get('invoice_date')
        due_date_str = request.form.get('due_date')

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
                'unit_price': float(unit_prices[i]),
            })

        if not customer_id or not items_data:
            flash('Please select a customer and at least one item.', 'danger')
            return redirect(url_for('sales.invoices'))

        invoice_date = datetime.fromisoformat(invoice_date_str) if invoice_date_str else datetime.now(timezone.utc)
        due_date = datetime.fromisoformat(due_date_str) if due_date_str else invoice_date

        invoice = Invoice(
            business_id=getattr(current_user, 'business_id', None),
            customer_id=int(customer_id),
            invoice_number=f"INV-{invoice_date.strftime('%Y%m%d')}-{datetime.now(timezone.utc).strftime('%H%M%S')}",
            invoice_date=invoice_date,
            due_date=due_date,
            subtotal=sum(float(item['quantity']) * float(item['unit_price']) for item in items_data),
            tax_amount=0.0,
            total_amount=sum(float(item['quantity']) * float(item['unit_price']) for item in items_data),
            status='issued',
            notes=notes,
        )
        db.session.add(invoice)
        db.session.flush()

        for item in items_data:
            db.session.add(InvoiceItem(
                invoice_id=invoice.id,
                product_id=item['product_id'],
                description=db.session.get(Product, item['product_id']).name if db.session.get(Product, item['product_id']) else None,
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                line_total=float(item['quantity']) * float(item['unit_price']),
            ))

        db.session.commit()
        flash(f'Invoice {invoice.invoice_number} created successfully.', 'success')
        return redirect(url_for('sales.invoices'))

    page = request.args.get('page', 1, type=int)
    customers = Customer.query.order_by(Customer.name.asc()).all()
    products = Product.query.order_by(Product.name.asc()).all()
    invoices = Invoice.query.order_by(Invoice.invoice_date.desc()).paginate(page=page, per_page=10)
    return render_template('invoices.html', customers=customers, products=products, invoices=invoices)


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

