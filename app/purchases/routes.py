import uuid
import json
from datetime import datetime, timezone

from flask import flash, redirect, render_template, request, url_for, abort
from flask_login import login_required, current_user

from models import Product, Purchase, PurchaseItem, Supplier, Payment, Staff, FinancialCategory, LineItem, Bill, db
from app.models.approval import ApprovalConfig, ApprovalRequest, ApprovalAction
from services.fifo_service import record_purchase
from app.auth.permissions import can_approve_at_level
from app.auth.decorators import role_required
from app.services.accounting_service import AccountingException, reverse_payment
from app.models import PurchaseReturn
from app.services.import_service import (
    PARTY_COLUMNS,
    ImportValidationError,
    import_suppliers,
)
from app.services.xlsx_import import XlsxParseError, parse_xlsx_file
from app.services.import_run_service import (
    commit_import,
    fail_import,
    flash_import_result,
    load_staged,
    normalize_date_order,
    purge_stale_staged_runs,
    stage_import,
    staged_records,
)
from app.services.purchase_return_service import (
    PurchaseReturnError,
    get_expenditure_returns,
    process_purchase_return,
    returnable_bills,
    reverse_purchase_return,
)

from . import purchases_bp


def _parse_date_arg(parameter):
    value = request.args.get(parameter, '').strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


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

        from app.services.approval_service import create_approval_request
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


@purchases_bp.route('/purchases/import/suppliers', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'accountant')
def import_suppliers_route():
    """Import suppliers from an Excel workbook with column mapping."""
    biz_id = getattr(current_user, 'business_id', None)

    def render_form(sheet_names, rows, import_run_id, preview):
        return render_template(
            'import_wizard.html',
            title='Map Supplier Columns' if rows else 'Import Suppliers',
            entity='suppliers',
            sheet_names=sheet_names,
            rows=rows,
            import_run_id=import_run_id,
            headers=list(rows[0].keys()) if rows else [],
            suggested=PARTY_COLUMNS,
            preview=preview,
            accounts=None,
            action=url_for('purchases.import_suppliers_route'),
            back_url=url_for('purchases.suppliers'),
            return_type='suppliers',
            mapping={},
        )

    if request.method == 'POST' and request.files.get('file'):
        upload = request.files.get('file')
        try:
            sheet_names, rows = parse_xlsx_file(upload)
        except XlsxParseError as error:
            flash(str(error), 'danger')
            return redirect(url_for('purchases.import_suppliers_route'))
        if not rows:
            flash('That workbook does not contain any data rows.', 'danger')
            return redirect(url_for('purchases.import_suppliers_route'))

        purge_stale_staged_runs()
        run = stage_import(
            biz_id,
            current_user.id,
            entity='suppliers',
            filename=getattr(upload, 'filename', None),
            rows=rows,
            date_order=request.form.get('date_order') or 'MDY',
        )
        db.session.commit()
        return render_form(sheet_names, rows, run.id, rows[:10])

    if request.method == 'POST' and request.form.get('mapping'):
        if request.form.get('payload'):
            flash(
                'This import session has expired. Upload the workbook again and map the columns.',
                'danger',
            )
            return redirect(url_for('purchases.import_suppliers_route'))

        run = load_staged(biz_id, request.form.get('import_run_id'))
        run_id = run.id
        run.date_order = normalize_date_order(request.form.get('date_order') or run.date_order)
        column_map = {
            field: request.form.get(f'map_{field}', '')
            for field in PARTY_COLUMNS
            if request.form.get(f'map_{field}', '')
        }
        try:
            result = import_suppliers(biz_id, staged_records(run), column_map)
            commit_import(biz_id, current_user.id, run, 'IMPORT_SUPPLIERS', result)
            db.session.commit()
        except ImportValidationError as error:
            db.session.rollback()
            fail_import(biz_id, current_user.id, run_id, 'IMPORT_SUPPLIERS_FAILED', error)
            db.session.commit()
            flash(str(error), 'danger')
        else:
            flash_import_result('Supplier', result, run)
        return redirect(url_for('purchases.suppliers'))

    return render_form([], [], None, [])


@purchases_bp.route('/purchases/returns', methods=['GET'])
@login_required
@role_required('admin', 'accountant')
def purchase_returns():
    """List expenditure returns with supplier and type filters."""
    biz_id = getattr(current_user, 'business_id', None)
    supplier_id = request.args.get('supplier_id', type=int)
    return_type = request.args.get('return_type', '').strip()
    start_date = _parse_date_arg('start_date')
    end_date = _parse_date_arg('end_date')

    report = get_expenditure_returns(
        biz_id,
        start_date=start_date,
        end_date=end_date,
        supplier_id=supplier_id,
        return_type=return_type or None,
    )
    return render_template(
        'purchase_returns.html',
        returns=report['items'],
        total_amount=report['total_amount'],
        suppliers=Supplier.query.filter_by(business_id=biz_id).order_by(Supplier.name.asc()).all(),
        supplier_id=supplier_id,
        return_type=return_type,
        start_date=request.args.get('start_date', ''),
        end_date=request.args.get('end_date', ''),
    )


@purchases_bp.route('/purchases/returns/new', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'accountant')
def purchase_return_new():
    """Create a bill credit note or cash refund against a received bill."""
    biz_id = getattr(current_user, 'business_id', None)

    if request.method == 'POST':
        bill_id = request.form.get('bill_id', '').strip()
        amount_raw = request.form.get('amount', '').strip()
        reason = request.form.get('reason', '').strip()
        return_type = request.form.get('return_type', 'credit_note').strip()
        try:
            bill_id = int(bill_id)
        except (TypeError, ValueError):
            db.session.rollback()
            flash('Select the bill being returned.', 'danger')
            return redirect(url_for('purchases.purchase_return_new'))

        try:
            purchase_return = process_purchase_return(
                biz_id,
                bill_id,
                amount_raw,
                reason,
                return_type=return_type,
                created_by=current_user.id,
            )
        except PurchaseReturnError as error:
            db.session.rollback()
            flash(str(error), 'danger')
        else:
            flash(f'Expenditure return #{purchase_return.id} recorded.', 'success')
            return redirect(url_for('purchases.purchase_return_view', return_id=purchase_return.id))

        return redirect(url_for('purchases.purchase_return_new'))

    bills = returnable_bills(biz_id)
    selected_bill_id = request.args.get('bill_id', type=int)
    selected = next(
        (entry for entry in bills if entry['bill'].id == selected_bill_id),
        None,
    )
    return render_template(
        'purchase_return_form.html',
        bills=bills,
        selected_bill=selected,
    )


@purchases_bp.route('/purchases/returns/<int:return_id>')
@login_required
@role_required('admin', 'accountant')
def purchase_return_view(return_id):
    """Show an expenditure return with its linked bill and journal entry."""
    biz_id = getattr(current_user, 'business_id', None)
    purchase_return = PurchaseReturn.query.filter_by(
        id=return_id,
        business_id=biz_id,
    ).first()
    if purchase_return is None:
        abort(404)

    return render_template(
        'purchase_return_view.html',
        purchase_return=purchase_return,
        journal_entry=purchase_return.journal_entry,
    )


@purchases_bp.route('/purchases/returns/<int:return_id>/reverse', methods=['POST'])
@login_required
@role_required('admin', 'accountant')
def purchase_return_reverse(return_id):
    """Reverse a posted expenditure return."""
    biz_id = getattr(current_user, 'business_id', None)
    reason = request.form.get('reason', '').strip()
    try:
        reverse_purchase_return(biz_id, return_id, reason, created_by=current_user.id)
    except PurchaseReturnError as error:
        db.session.rollback()
        flash(str(error), 'danger')
    else:
        flash('Expenditure return reversed.', 'success')
    return redirect(url_for('purchases.purchase_return_view', return_id=return_id))


@purchases_bp.route('/payments/<int:payment_id>/refund', methods=['POST'])
@login_required
@role_required('admin')
def payment_refund(payment_id):
    """Refund a payment in full or in part."""
    biz_id = getattr(current_user, 'business_id', None)
    payment = db.session.get(Payment, payment_id)
    if not payment or payment.business_id != biz_id:
        abort(404)

    reason = request.form.get('reason', '').strip()
    amount_raw = request.form.get('refund_amount', '').strip()

    try:
        if amount_raw:
            refund_amount = float(amount_raw)
        else:
            refund_amount = None
        reversal = reverse_payment(
            biz_id,
            payment.id,
            reason,
            created_by=current_user.id,
            amount=refund_amount,
        )
    except AccountingException as error:
        db.session.rollback()
        flash(str(error), 'danger')
    else:
        flash(f'Payment refunded with journal entry #{reversal.id}.', 'success')

    return redirect(url_for('purchases.payments'))


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