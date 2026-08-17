import uuid
import json
from datetime import datetime, timezone

from flask import flash, redirect, render_template, request, url_for, abort
from flask_login import login_required, current_user

from models import Product, Purchase, PurchaseItem, Supplier, Payment, Staff, FinancialCategory, LineItem, Bill, db
from app.models.approval import ApprovalConfig, ApprovalRequest, ApprovalAction
from services.fifo_service import record_purchase
from app.auth.permissions import can_approve_at_level

from . import purchases_bp


@purchases_bp.route('/payments/status/<int:payment_id>')
@login_required
def payment_status(payment_id):
    """View the approval status of a specific payment."""
    biz_id = getattr(current_user, 'business_id', None)
    payment = db.session.get(Payment, payment_id)
    if not payment or payment.business_id != biz_id:
        abort(404)
    
    approval_req = ApprovalRequest.query.filter_by(
        business_id=biz_id,
        transaction_type='payment',
        transaction_id=payment.id,
    ).first()
    
    return render_template('payment_status.html', payment=payment, approval_request=approval_req)


@purchases_bp.route('/suppliers', methods=['GET', 'POST'])
@login_required
def suppliers():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Supplier name is required.', 'danger')
            return redirect(url_for('purchases.suppliers'))

        business_id = getattr(current_user, 'business_id', None)
        
        # Check if supplier with same name exists
        supplier = Supplier.query.filter_by(business_id=business_id, name=name).first()
        if not supplier:
            # Generate unique supplier ID
            supplier_id = f"SUPP-{uuid.uuid4().hex[:8].upper()}"
            supplier = Supplier(
                business_id=business_id,
                name=name,
                supplier_id=supplier_id,
                phone=request.form.get('phone', '').strip() or None,
                email=request.form.get('email', '').strip() or None,
                address=request.form.get('address', '').strip() or None,
                bank_name=request.form.get('bank_name', '').strip() or None,
                bank_branch=request.form.get('bank_branch', '').strip() or None,
                bank_account_number=request.form.get('bank_account_number', '').strip() or None,
                payment_terms=request.form.get('payment_terms', '').strip() or None,
                is_active=True
            )
            db.session.add(supplier)
            db.session.commit()
            flash(f'Supplier "{name}" added successfully!', 'success')
        else:
            flash(f'Supplier "{name}" already exists.', 'info')
        return redirect(url_for('purchases.suppliers'))

    biz_id = getattr(current_user, 'business_id', None)
    search_query = request.args.get('search', '').strip()
    suppliers = Supplier.query.filter_by(business_id=biz_id).order_by(Supplier.name.asc()).all()

    if search_query:
        suppliers = [s for s in suppliers if search_query.lower() in s.name.lower() or 
                     (s.email and search_query.lower() in s.email.lower()) or
                     (s.phone and search_query in s.phone)]
    
    return render_template('suppliers.html', suppliers=suppliers, search_query=search_query)


@purchases_bp.route('/payments', methods=['GET', 'POST'])
@login_required
def payments():
    if request.method == 'POST':
        payee_type = request.form.get('payee_type', 'supplier').strip()
        supplier_id = request.form.get('supplier_id', '').strip()
        bill_id = request.form.get('bill_id', '').strip()
        staff_id = request.form.get('staff_id', '').strip()
        category_id = request.form.get('category_id', '').strip()
        line_item_id = request.form.get('line_item_id', '').strip()
        description = request.form.get('description', '').strip()
        amount = request.form.get('amount', '').strip()
        payment_mode = request.form.get('payment_mode', 'cash').strip()
        reference = request.form.get('reference', '').strip()

        if not amount or float(amount) <= 0:
            flash('A positive payment amount is required.', 'danger')
            return redirect(url_for('purchases.payments'))

        if payee_type == 'supplier' and not supplier_id:
            flash('Please select a supplier for the payment.', 'danger')
            return redirect(url_for('purchases.payments'))

        if payee_type == 'staff' and not staff_id:
            flash('Please select a staff member for the payment.', 'danger')
            return redirect(url_for('purchases.payments'))

        if not category_id or not line_item_id:
            flash('Please select a financial category and line item.', 'danger')
            return redirect(url_for('purchases.payments'))

        biz_id = getattr(current_user, 'business_id', None)

        payment = Payment(
            business_id=biz_id,
            supplier_id=int(supplier_id) if supplier_id else None,
            bill_id=int(bill_id) if bill_id else None,
            staff_id=int(staff_id) if staff_id else None,
            category_id=int(category_id) if category_id else None,
            line_item_id=int(line_item_id) if line_item_id else None,
            payee_type=payee_type,
            description=description or None,
            payment_date=datetime.now(timezone.utc),
            amount=float(amount),
            payment_mode=payment_mode or 'cash',
            reference=reference or None,
            status='pending',
        )
        db.session.add(payment)
        db.session.flush()

        from app.approvals.routes import create_approval_request
        approval_req = create_approval_request(
            business_id=biz_id,
            transaction_type='payment',
            transaction_id=payment.id,
            created_by=current_user.id,
        )

        if approval_req:
            db.session.commit()
            flash('Payment submitted for approval. It will be processed once approved.', 'info')
        else:
            from services.fifo_service import _post_payment_accounting
            _post_payment_accounting(
                payment_date=payment.payment_date,
                amount=float(amount),
                payment_id=payment.id,
                business_id=biz_id,
                created_by=current_user.id,
                category_id=int(category_id) if category_id else None,
                line_item_id=int(line_item_id) if line_item_id else None,
                payee_type=payee_type,
            )
            payment.status = 'approved'
            db.session.commit()
            flash('Payment recorded successfully.', 'success')

        return redirect(url_for('purchases.payments'))

    page = request.args.get('page', 1, type=int)
    biz_id = getattr(current_user, 'business_id', None)
    suppliers = Supplier.query.filter_by(business_id=biz_id).order_by(Supplier.name.asc()).all()
    staff_members = Staff.query.filter_by(business_id=biz_id).order_by(Staff.name.asc()).all()
    categories = FinancialCategory.query.filter_by(business_id=biz_id).order_by(FinancialCategory.sort_order.asc()).all()
    line_items = LineItem.query.filter_by(business_id=biz_id).order_by(LineItem.sort_order.asc()).all()
    bills = Bill.query.filter(Bill.business_id == biz_id).order_by(Bill.bill_date.desc()).all()
    payments = Payment.query.filter_by(business_id=biz_id).order_by(Payment.payment_date.desc()).paginate(page=page, per_page=10)

    import json
    line_items_json = json.dumps([{
        'id': item.id,
        'name': item.name,
        'category_id': item.category_id
    } for item in line_items])

    return render_template('payments.html',
                         suppliers=suppliers,
                         staff_members=staff_members,
                         categories=categories,
                         line_items=line_items,
                         line_items_json=line_items_json,
                         payments=payments,
                         bills=bills)


@purchases_bp.route('/purchases', methods=['GET', 'POST'])
@login_required
def purchases():
    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id', '').strip()
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

        # Validate supplier exists
        supplier_name = None
        if supplier_id:
            supplier = db.session.get(Supplier, int(supplier_id))
            if not supplier or supplier.business_id != current_user.business_id:
                flash('Invalid supplier selected.', 'danger')
                return redirect(url_for('purchases.purchases'))
            supplier_name = supplier.name

        try:
            record_purchase(purchase_date, supplier_name, notes, items_data, current_user.business_id, current_user.id)
            flash('Inventory purchase recorded successfully and stock updated!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording purchase: {str(e)}', 'danger')

        return redirect(url_for('purchases.purchases'))

    biz_id = getattr(current_user, 'business_id', None)
    products = Product.query.filter_by(business_id=biz_id).order_by(Product.name.asc()).all()
    page = request.args.get('page', 1, type=int)
    purchase_records = Purchase.query.filter_by(business_id=biz_id).order_by(Purchase.purchase_date.desc()).paginate(page=page, per_page=10)
    return render_template('purchases.html', products=products, purchases=purchase_records)


@purchases_bp.route('/suppliers/<int:supplier_id>/edit', methods=['POST'])
@login_required
def edit_supplier(supplier_id):
    supplier = db.session.get(Supplier, supplier_id)
    if not supplier or supplier.business_id != getattr(current_user, 'business_id', None):
        abort(404)

    biz_id = getattr(current_user, 'business_id', None)
    import json
    data = json.dumps({
        'name': request.form.get('name', '').strip(),
        'phone': request.form.get('phone', '').strip() or None,
        'email': request.form.get('email', '').strip() or None,
        'address': request.form.get('address', '').strip() or None,
        'bank_name': request.form.get('bank_name', '').strip() or None,
        'bank_branch': request.form.get('bank_branch', '').strip() or None,
        'bank_account_number': request.form.get('bank_account_number', '').strip() or None,
        'payment_terms': request.form.get('payment_terms', '').strip() or None,
    })

    req = ApprovalRequest(
        business_id=biz_id,
        transaction_type='supplier_edit',
        transaction_id=supplier.id,
        current_level=0,
        status='pending',
        data=data,
        created_by=current_user.id,
    )
    db.session.add(req)
    db.session.commit()
    flash('Supplier edit request submitted for approval.', 'success')
    return redirect(url_for('purchases.suppliers'))


@purchases_bp.route('/suppliers/<int:supplier_id>/delete', methods=['POST'])
@login_required
def delete_supplier(supplier_id):
    supplier = db.session.get(Supplier, supplier_id)
    if not supplier or supplier.business_id != getattr(current_user, 'business_id', None):
        abort(404)

    biz_id = getattr(current_user, 'business_id', None)
    req = ApprovalRequest(
        business_id=biz_id,
        transaction_type='supplier_delete',
        transaction_id=supplier.id,
        current_level=0,
        status='pending',
        created_by=current_user.id,
    )
    db.session.add(req)
    db.session.commit()
    flash('Supplier delete request submitted for approval.', 'success')
    return redirect(url_for('purchases.suppliers'))