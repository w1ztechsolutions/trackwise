import uuid
import json
from datetime import datetime, timezone
from flask_login import login_required, current_user
from flask import flash, redirect, render_template, request, url_for, abort

from models import Product, Sale, SaleItem, Customer, Invoice, InvoiceItem, Receipt, db
from app.models.approval import ApprovalRequest
from services.fifo_service import InventoryException, record_sale, get_tax_rate
from app.services.accounting_service import AccountingException, post_entry, get_account_by_code

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
        
        # Check if customer with same name exists
        customer = Customer.query.filter_by(business_id=business_id, name=name).first()
        if not customer:
            # Generate unique customer ID
            customer_id = f"CUST-{uuid.uuid4().hex[:8].upper()}"
            customer = Customer(
                business_id=business_id,
                name=name,
                customer_id=customer_id,
                phone=request.form.get('phone', '').strip() or None,
                email=request.form.get('email', '').strip() or None,
                address=request.form.get('address', '').strip() or None,
                bank_name=request.form.get('bank_name', '').strip() or None,
                bank_branch=request.form.get('bank_branch', '').strip() or None,
                bank_account_number=request.form.get('bank_account_number', '').strip() or None,
                is_active=True
            )
            db.session.add(customer)
            db.session.commit()
            flash(f'Customer "{name}" added successfully!', 'success')
        else:
            flash(f'Customer "{name}" already exists.', 'info')
        return redirect(url_for('sales.customers'))

    search_query = request.args.get('search', '').strip()
    customers = Customer.query.order_by(Customer.name.asc()).all()
    
    if search_query:
        customers = [c for c in customers if search_query.lower() in c.name.lower() or 
                     (c.email and search_query.lower() in c.email.lower()) or
                     (c.phone and search_query in c.phone)]
    
    return render_template('customers.html', customers=customers, search_query=search_query)


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
        tax_rates = request.form.getlist('tax_rate[]')

        biz_id = getattr(current_user, 'business_id', None)
        default_tax_rate = get_tax_rate(business_id=biz_id)

        items_data = []
        line_items_data = []
        subtotal = 0.0
        total_tax = 0.0
        for i in range(len(product_ids)):
            if not product_ids[i] or not quantities[i] or not unit_prices[i]:
                continue
            qty = int(quantities[i])
            unit_price = float(unit_prices[i])
            line_total = qty * unit_price
            try:
                rate = float(tax_rates[i]) if i < len(tax_rates) and tax_rates[i] else float(default_tax_rate)
            except (TypeError, ValueError):
                rate = float(default_tax_rate)
            line_tax = round(line_total * (rate / 100.0), 2)
            subtotal += line_total
            total_tax += line_tax
            items_data.append({
                'product_id': int(product_ids[i]),
                'quantity': qty,
                'unit_price': unit_price,
            })
            line_items_data.append({
                'product_id': int(product_ids[i]),
                'quantity': qty,
                'unit_price': unit_price,
                'line_total': line_total,
                'tax_rate': rate,
                'tax_amount': line_tax,
            })

        if not customer_id or not items_data:
            flash('Please select a customer and at least one item.', 'danger')
            return redirect(url_for('sales.invoices'))

        invoice_date = datetime.fromisoformat(invoice_date_str) if invoice_date_str else datetime.now(timezone.utc)
        due_date = datetime.fromisoformat(due_date_str) if due_date_str else invoice_date

        invoice = Invoice(
            business_id=biz_id,
            customer_id=int(customer_id),
            invoice_number=f"INV-{invoice_date.strftime('%Y%m%d')}-{datetime.now(timezone.utc).strftime('%H%M%S')}",
            invoice_date=invoice_date,
            due_date=due_date,
            subtotal=round(subtotal, 2),
            tax_amount=round(total_tax, 2),
            total_amount=round(subtotal + total_tax, 2),
            status='issued',
            notes=notes,
        )
        db.session.add(invoice)
        db.session.flush()

        for li in line_items_data:
            product = db.session.get(Product, li['product_id'])
            db.session.add(InvoiceItem(
                business_id=biz_id,
                invoice_id=invoice.id,
                product_id=li['product_id'],
                description=product.name if product else None,
                quantity=li['quantity'],
                unit_price=li['unit_price'],
                line_total=li['line_total'],
                tax_rate=li['tax_rate'],
                tax_amount=li['tax_amount'],
                tax_inclusive=False,
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
        customer = request.form.get('customer_name', '').strip()
        sale_date_str = request.form.get('sale_date')
        invoice_id_raw = request.form.get('invoice_id', '').strip()

        sale_date = None
        if sale_date_str:
            sale_date = datetime.fromisoformat(sale_date_str)

        invoice_id = int(invoice_id_raw) if invoice_id_raw else None

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
            tax_amount = 0.0
            if invoice_id:
                invoice = db.session.get(Invoice, invoice_id)
                if invoice and invoice.business_id == current_user.business_id:
                    tax_amount = float(invoice.tax_amount or 0)
            record_sale(
                sale_date,
                customer,
                items_data,
                current_user.business_id,
                current_user.id,
                invoice_id=invoice_id,
                tax_amount=tax_amount,
            )
            flash('Sale recorded successfully! Stock and COGS calculations updated.', 'success')
        except InventoryException as ie:
            db.session.rollback()
            flash(f'Inventory Error: {str(ie)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording sale: {str(e)}', 'danger')

        return redirect(url_for('sales.sales'))

    products = Product.query.filter(Product.quantity_in_stock > 0).order_by(Product.name.asc()).all()
    invoices = Invoice.query.order_by(Invoice.invoice_date.desc()).all()
    page = request.args.get('page', 1, type=int)
    sale_records = Sale.query.order_by(Sale.sale_date.desc()).paginate(page=page, per_page=10)
    return render_template('sales.html', products=products, sales=sale_records, invoices=invoices)


@sales_bp.route('/invoices/<int:invoice_id>/receipt')
@login_required
def invoice_receipt(invoice_id):
    invoice = db.session.get(Invoice, invoice_id)
    if invoice is None or invoice.business_id != getattr(current_user, 'business_id', None):
        abort(404)
    return render_template('document_receipt.html', receipt_type='invoice', invoice=invoice, sale=None)


@sales_bp.route('/sales/<int:sale_id>/receipt')
@login_required
def sale_receipt(sale_id):
    sale = db.session.get(Sale, sale_id)
    if sale is None or sale.business_id != getattr(current_user, 'business_id', None):
        abort(404)
    return render_template('document_receipt.html', receipt_type='sale', sale=sale, invoice=sale.invoice)


@sales_bp.route('/customers/<int:customer_id>/edit', methods=['POST'])
@login_required
def edit_customer(customer_id):
    customer = db.session.get(Customer, customer_id)
    if not customer or customer.business_id != getattr(current_user, 'business_id', None):
        abort(404)

    biz_id = getattr(current_user, 'business_id', None)
    data = json.dumps({
        'name': request.form.get('name', '').strip(),
        'phone': request.form.get('phone', '').strip() or None,
        'email': request.form.get('email', '').strip() or None,
        'address': request.form.get('address', '').strip() or None,
        'bank_name': request.form.get('bank_name', '').strip() or None,
        'bank_branch': request.form.get('bank_branch', '').strip() or None,
        'bank_account_number': request.form.get('bank_account_number', '').strip() or None,
    })

    req = ApprovalRequest(
        business_id=biz_id,
        transaction_type='customer_edit',
        transaction_id=customer.id,
        current_level=0,
        status='pending',
        data=data,
        created_by=current_user.id,
    )
    db.session.add(req)
    db.session.commit()
    flash('Customer edit request submitted for approval.', 'success')
    return redirect(url_for('sales.customers'))


@sales_bp.route('/customers/<int:customer_id>/delete', methods=['POST'])
@login_required
def delete_customer(customer_id):
    customer = db.session.get(Customer, customer_id)
    if not customer or customer.business_id != getattr(current_user, 'business_id', None):
        abort(404)

    biz_id = getattr(current_user, 'business_id', None)
    req = ApprovalRequest(
        business_id=biz_id,
        transaction_type='customer_delete',
        transaction_id=customer.id,
        current_level=0,
        status='pending',
        created_by=current_user.id,
    )
    db.session.add(req)
    db.session.commit()
    flash('Customer delete request submitted for approval.', 'success')
    return redirect(url_for('sales.customers'))


# ─── Invoice Lifecycle ────────────────────────────────────────────────────

@sales_bp.route('/invoices/<int:invoice_id>/send', methods=['POST'])
@login_required
def invoice_send(invoice_id):
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice or invoice.business_id != getattr(current_user, 'business_id', None):
        abort(404)
    if invoice.status not in ('draft', 'issued'):
        flash('Invoice can only be sent from draft or issued status.', 'danger')
        return redirect(url_for('sales.invoices'))
    invoice.status = 'sent'
    db.session.commit()
    flash(f'Invoice {invoice.invoice_number} marked as sent.', 'success')
    return redirect(url_for('sales.invoices'))


@sales_bp.route('/invoices/<int:invoice_id>/mark-paid', methods=['POST'])
@login_required
def invoice_mark_paid(invoice_id):
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice or invoice.business_id != getattr(current_user, 'business_id', None):
        abort(404)
    if invoice.status in ('paid', 'void'):
        flash('Invoice is already paid or void.', 'danger')
        return redirect(url_for('sales.invoices'))

    amount_raw = request.form.get('amount', '').strip()
    try:
        amount = float(amount_raw) if amount_raw else float(invoice.total_amount or 0)
    except (TypeError, ValueError):
        flash('Invalid payment amount.', 'danger')
        return redirect(url_for('sales.invoices'))

    payment_method = request.form.get('payment_method', 'cash').strip() or 'cash'
    reference = request.form.get('reference', '').strip() or None
    notes = request.form.get('notes', '').strip() or None

    biz_id = getattr(current_user, 'business_id', None)
    receipt_date = datetime.now(timezone.utc)

    receipt = Receipt(
        business_id=biz_id,
        customer_id=invoice.customer_id,
        invoice_id=invoice.id,
        receipt_date=receipt_date,
        amount=amount,
        payment_method=payment_method,
        reference=reference,
        notes=notes,
    )
    db.session.add(receipt)
    db.session.flush()

    # Post accounting: Dr Cash / Cr AR
    cash_acct = get_account_by_code(biz_id, '1000')
    ar_acct = get_account_by_code(biz_id, '1200')
    lines = []
    if cash_acct:
        lines.append({'account_id': cash_acct.id, 'debit_amount': amount, 'credit_amount': 0})
    if ar_acct:
        lines.append({'account_id': ar_acct.id, 'debit_amount': 0, 'credit_amount': amount})

    if len(lines) >= 2:
        try:
            post_entry(
                biz_id,
                receipt_date,
                f"Receipt #{receipt.id} for Invoice #{invoice.invoice_number}",
                lines,
                reference_type='Receipt',
                reference_id=receipt.id,
                created_by=current_user.id,
            )
        except AccountingException as e:
            db.session.rollback()
            flash(str(e), 'danger')
            return redirect(url_for('sales.invoices'))

    if amount >= float(invoice.total_amount or 0):
        invoice.status = 'paid'
    else:
        invoice.status = 'partially_paid'

    db.session.commit()
    flash(f'Payment of {amount:.2f} recorded for Invoice {invoice.invoice_number}.', 'success')
    return redirect(url_for('sales.invoices'))


@sales_bp.route('/invoices/<int:invoice_id>/void', methods=['POST'])
@login_required
def invoice_void(invoice_id):
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice or invoice.business_id != getattr(current_user, 'business_id', None):
        abort(404)
    if invoice.status == 'void':
        flash('Invoice is already void.', 'info')
        return redirect(url_for('sales.invoices'))
    if invoice.status == 'paid':
        flash('Cannot void a paid invoice. Create a credit note instead.', 'danger')
        return redirect(url_for('sales.invoices'))

    invoice.status = 'void'
    db.session.commit()
    flash(f'Invoice {invoice.invoice_number} has been voided.', 'warning')
    return redirect(url_for('sales.invoices'))


@sales_bp.route('/credit-notes', methods=['GET', 'POST'])
@login_required
def credit_notes():
    biz_id = getattr(current_user, 'business_id', None)

    if request.method == 'POST':
        invoice_id = request.form.get('invoice_id', '').strip()
        amount_raw = request.form.get('amount', '').strip()
        reason = request.form.get('reason', '').strip()
        apply_to_ar = request.form.get('apply_to_ar') == 'on'

        if not invoice_id or not amount_raw:
            flash('Invoice and amount are required.', 'danger')
            return redirect(url_for('sales.credit_notes'))

        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            flash('Invalid amount.', 'danger')
            return redirect(url_for('sales.credit_notes'))

        invoice = db.session.get(Invoice, int(invoice_id))
        if not invoice or invoice.business_id != biz_id:
            flash('Invalid invoice.', 'danger')
            return redirect(url_for('sales.credit_notes'))

        if amount <= 0 or amount > float(invoice.total_amount or 0):
            flash('Amount must be between 0 and invoice total.', 'danger')
            return redirect(url_for('sales.credit_notes'))

        receipt_date = datetime.now(timezone.utc)

        # Create a negative receipt (credit note)
        receipt = Receipt(
            business_id=biz_id,
            customer_id=invoice.customer_id,
            invoice_id=invoice.id,
            receipt_date=receipt_date,
            amount=-amount,
            payment_method='credit_note',
            reference=f"CN-{invoice.invoice_number}",
            notes=reason or 'Credit note',
        )
        db.session.add(receipt)
        db.session.flush()

        if apply_to_ar:
            cash_acct = get_account_by_code(biz_id, '1000')
            ar_acct = get_account_by_code(biz_id, '1200')
            lines = []
            if ar_acct:
                lines.append({'account_id': ar_acct.id, 'debit_amount': amount, 'credit_amount': 0})
            if cash_acct:
                lines.append({'account_id': cash_acct.id, 'debit_amount': 0, 'credit_amount': amount})
            if len(lines) >= 2:
                try:
                    post_entry(
                        biz_id,
                        receipt_date,
                        f"Credit Note #{receipt.id} for Invoice #{invoice.invoice_number}",
                        lines,
                        reference_type='Receipt',
                        reference_id=receipt.id,
                        created_by=current_user.id,
                    )
                except AccountingException as e:
                    db.session.rollback()
                    flash(str(e), 'danger')
                    return redirect(url_for('sales.credit_notes'))

        invoice.status = 'credit_note_issued'
        db.session.commit()
        flash(f'Credit note of {amount:.2f} issued for Invoice {invoice.invoice_number}.', 'success')
        return redirect(url_for('sales.credit_notes'))

    page = request.args.get('page', 1, type=int)
    customers = Customer.query.order_by(Customer.name.asc()).all()
    invoices = Invoice.query.filter(
        Invoice.business_id == biz_id,
        Invoice.status.in_(('issued', 'sent', 'partially_paid', 'paid'))
    ).order_by(Invoice.invoice_date.desc()).paginate(page=page, per_page=10)
    return render_template('credit_notes.html', customers=customers, invoices=invoices)


# ─── AR Payment Application ───────────────────────────────────────────────

@sales_bp.route('/invoices/<int:invoice_id>/apply-payment', methods=['GET', 'POST'])
@login_required
def apply_payment_to_invoice(invoice_id):
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice or invoice.business_id != getattr(current_user, 'business_id', None):
        abort(404)

    if request.method == 'GET':
        return render_template('apply_payment.html', invoice=invoice)

    if invoice.status in ('paid', 'void'):
        flash('Invoice is already paid or void.', 'danger')
        return redirect(url_for('sales.invoices'))

    amount_raw = request.form.get('amount', '').strip()
    try:
        amount = float(amount_raw) if amount_raw else float(invoice.total_amount or 0)
    except (TypeError, ValueError):
        flash('Invalid payment amount.', 'danger')
        return redirect(url_for('sales.invoices'))

    if amount <= 0:
        flash('Payment amount must be positive.', 'danger')
        return redirect(url_for('sales.invoices'))

    biz_id = getattr(current_user, 'business_id', None)
    receipt_date = datetime.now(timezone.utc)
    payment_method = request.form.get('payment_method', 'cash').strip() or 'cash'
    reference = request.form.get('reference', '').strip() or None
    notes = request.form.get('notes', '').strip() or None

    receipt = Receipt(
        business_id=biz_id,
        customer_id=invoice.customer_id,
        invoice_id=invoice.id,
        receipt_date=receipt_date,
        amount=amount,
        payment_method=payment_method,
        reference=reference,
        notes=notes,
    )
    db.session.add(receipt)
    db.session.flush()

    cash_acct = get_account_by_code(biz_id, '1000')
    ar_acct = get_account_by_code(biz_id, '1200')
    lines = []
    if cash_acct:
        lines.append({'account_id': cash_acct.id, 'debit_amount': amount, 'credit_amount': 0})
    if ar_acct:
        lines.append({'account_id': ar_acct.id, 'debit_amount': 0, 'credit_amount': amount})

    if len(lines) >= 2:
        try:
            post_entry(
                biz_id,
                receipt_date,
                f"AR Payment #{receipt.id} applied to Invoice #{invoice.invoice_number}",
                lines,
                reference_type='Receipt',
                reference_id=receipt.id,
                created_by=current_user.id,
            )
        except AccountingException as e:
            db.session.rollback()
            flash(str(e), 'danger')
            return redirect(url_for('sales.invoices'))

    invoice_total = float(invoice.total_amount or 0)
    if amount >= invoice_total:
        invoice.status = 'paid'
    else:
        invoice.status = 'partially_paid'

    db.session.commit()
    flash(f'Payment of {amount:.2f} applied to Invoice {invoice.invoice_number}.', 'success')
    return redirect(url_for('sales.invoices'))

