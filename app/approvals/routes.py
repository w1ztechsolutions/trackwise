"""Approval workflow routes — configuration and transaction approval processing."""

import json
from datetime import datetime, timezone

from flask import (
    abort, flash, jsonify, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required

from app.models import db
from app.auth.permissions import permission_required, can_approve_at_level
from app.models.approval import ApprovalConfig, ApprovalRequest, ApprovalAction
from models import Supplier, Customer

from . import approvals_bp


# ─── Admin: Approval Workflow Configuration ────────────────────────────────

@approvals_bp.route('/config')
@login_required
@permission_required('manage_settings')
def list_configs():
    """List all approval workflow configurations for the current business."""
    biz_id = getattr(current_user, 'business_id', None)
    if not biz_id:
        abort(404)

    configs = ApprovalConfig.query.filter_by(business_id=biz_id).all()
    return render_template('approval_configs.html', configs=configs)


@approvals_bp.route('/config/create', methods=['GET', 'POST'])
@login_required
@permission_required('manage_settings')
def create_config():
    """Create a new approval workflow configuration."""
    biz_id = getattr(current_user, 'business_id', None)
    if not biz_id:
        abort(404)

    if current_user.role != 'admin':
        flash('Only administrators can configure approval workflows.', 'danger')
        return redirect(url_for('approvals.list_configs'))

    if request.method == 'POST':
        transaction_type = request.form.get('transaction_type', '').strip()
        levels_raw = request.form.getlist('levels[]')

        if not transaction_type:
            flash('Transaction type is required.', 'danger')
            return render_template('approval_config_form.html', approval_config=None)

        # Validate levels
        valid_roles = ['accountant', 'manager']
        levels = [r for r in levels_raw if r in valid_roles]

        if not levels:
            flash('At least one approval level is required.', 'danger')
            return render_template('approval_config_form.html', approval_config=None)

        existing = ApprovalConfig.query.filter_by(
            business_id=biz_id, transaction_type=transaction_type
        ).first()
        if existing:
            flash(f'Configuration for "{transaction_type}" already exists. Edit it instead.', 'warning')
            return redirect(url_for('approvals.edit_config', config_id=existing.id))

        config = ApprovalConfig(
            business_id=biz_id,
            transaction_type=transaction_type,
            levels=json.dumps(levels),
            is_active=True,
        )
        db.session.add(config)
        db.session.commit()

        flash(f'Approval workflow for "{transaction_type}" created.', 'success')
        return redirect(url_for('approvals.list_configs'))

    return render_template('approval_config_form.html', approval_config=None)


@approvals_bp.route('/config/<int:config_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('manage_settings')
def edit_config(config_id):
    """Edit an existing approval workflow configuration."""
    biz_id = getattr(current_user, 'business_id', None)
    config = db.session.get(ApprovalConfig, config_id)
    if not config or config.business_id != biz_id:
        abort(404)

    if current_user.role != 'admin':
        flash('Only administrators can configure approval workflows.', 'danger')
        return redirect(url_for('approvals.list_configs'))

    if request.method == 'POST':
        levels_raw = request.form.getlist('levels[]')
        valid_roles = ['accountant', 'manager']
        levels = [r for r in levels_raw if r in valid_roles]

        if not levels:
            flash('At least one approval level is required.', 'danger')
            return render_template('approval_config_form.html', approval_config=config)

        config.levels = json.dumps(levels)
        config.is_active = request.form.get('is_active') == 'on'
        db.session.commit()

        flash(f'Approval workflow for "{config.transaction_type}" updated.', 'success')
        return redirect(url_for('approvals.list_configs'))

    return render_template('approval_config_form.html', approval_config=config)


@approvals_bp.route('/config/<int:config_id>/delete', methods=['POST'])
@login_required
@permission_required('manage_settings')
def delete_config(config_id):
    """Delete an approval workflow configuration."""
    biz_id = getattr(current_user, 'business_id', None)
    config = db.session.get(ApprovalConfig, config_id)
    if not config or config.business_id != biz_id:
        abort(404)

    db.session.delete(config)
    db.session.commit()
    flash(f'Approval workflow for "{config.transaction_type}" deleted.', 'success')
    return redirect(url_for('approvals.list_configs'))


# ─── Approval Processing ───────────────────────────────────────────────────

@approvals_bp.route('/pending')
@login_required
def pending_approvals():
    """Show pending approvals for the current user based on their role."""
    biz_id = getattr(current_user, 'business_id', None)
    if not biz_id:
        abort(404)

    role = getattr(current_user, 'role', 'viewer')
    if role not in ('accountant', 'manager', 'admin'):
        flash('You do not have permission to view pending approvals.', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    # Get all pending approval requests for this business
    pending = ApprovalRequest.query.filter_by(
        business_id=biz_id, status='pending'
    ).order_by(ApprovalRequest.created_at.desc()).all()

    # Filter by what this user can act on
    actionable = []
    for req in pending:
        if can_approve_at_level(current_user, req.current_level):
            actionable.append(req)

    return render_template('pending_approvals.html', requests=actionable)


@approvals_bp.route('/<int:request_id>/approve', methods=['POST'])
@login_required
def approve_request(request_id):
    """Approve a pending approval request at the current level."""
    biz_id = getattr(current_user, 'business_id', None)
    req = db.session.get(ApprovalRequest, request_id)
    if not req or req.business_id != biz_id:
        abort(404)

    if req.status != 'pending':
        flash('This request has already been processed.', 'warning')
        return redirect(url_for('approvals.pending_approvals'))

    if not can_approve_at_level(current_user, req.current_level):
        flash('You do not have permission to approve at this level.', 'danger')
        return redirect(url_for('approvals.pending_approvals'))

    comment = request.form.get('comment', '').strip()

    # Record the approval action
    action = ApprovalAction(
        approval_request_id=req.id,
        actor_id=current_user.id,
        action='approved',
        level=req.current_level,
        comment=comment or None,
    )
    db.session.add(action)

    # Check if there are more levels
    import json
    config = ApprovalConfig.query.filter_by(
        business_id=req.business_id,
        transaction_type=req.transaction_type,
    ).first()
    levels = json.loads(config.levels) if config and config.levels else []

    if req.current_level + 1 >= len(levels):
        # All levels approved — mark as completed and execute
        req.status = 'completed'
        req.completed_at = datetime.now(timezone.utc)
        _execute_approval(req)
        flash('Transaction fully approved and executed.', 'success')
    else:
        # Move to next level
        req.current_level += 1
        flash(f'Approved at level {req.current_level}. Moved to next approver.', 'success')

    db.session.commit()
    return redirect(url_for('approvals.pending_approvals'))


@approvals_bp.route('/<int:request_id>/reject', methods=['POST'])
@login_required
def reject_request(request_id):
    """Reject a pending approval request."""
    biz_id = getattr(current_user, 'business_id', None)
    req = db.session.get(ApprovalRequest, request_id)
    if not req or req.business_id != biz_id:
        abort(404)

    if req.status != 'pending':
        flash('This request has already been processed.', 'warning')
        return redirect(url_for('approvals.pending_approvals'))

    if not can_approve_at_level(current_user, req.current_level):
        flash('You do not have permission to reject at this level.', 'danger')
        return redirect(url_for('approvals.pending_approvals'))

    comment = request.form.get('comment', '').strip()

    action = ApprovalAction(
        approval_request_id=req.id,
        actor_id=current_user.id,
        action='rejected',
        level=req.current_level,
        comment=comment or None,
    )
    db.session.add(action)
    req.status = 'rejected'
    req.completed_at = datetime.now(timezone.utc)
    db.session.commit()

    flash('Transaction rejected.', 'warning')
    return redirect(url_for('approvals.pending_approvals'))


@approvals_bp.route('/history')
@login_required
def approval_history():
    """Show completed/rejected approval requests for the current business."""
    biz_id = getattr(current_user, 'business_id', None)
    if not biz_id:
        abort(404)

    completed = ApprovalRequest.query.filter(
        ApprovalRequest.business_id == biz_id,
        ApprovalRequest.status.in_(['completed', 'rejected']),
    ).order_by(ApprovalRequest.completed_at.desc()).limit(50).all()

    return render_template('approval_history.html', requests=completed)


# ─── Helper: Create an approval request (called from transaction routes) ───

def create_approval_request(business_id, transaction_type, transaction_id, created_by):
    """Create an approval request for a transaction if approval workflow is configured.

    Returns the ApprovalRequest if created, or None if no approval is needed.
    """
    config = ApprovalConfig.query.filter_by(
        business_id=business_id,
        transaction_type=transaction_type,
        is_active=True,
    ).first()

    if not config:
        return None  # No approval needed

    import json
    levels = json.loads(config.levels) if config.levels else []
    if not levels:
        return None  # No levels configured

    req = ApprovalRequest(
        business_id=business_id,
        transaction_type=transaction_type,
        transaction_id=transaction_id,
        current_level=0,
        status='pending',
        created_by=created_by,
    )
    db.session.add(req)
    db.session.commit()
    return req


def _execute_approval(req):
    """Execute the actual action when an approval request is fully approved."""
    transaction_type = req.transaction_type
    transaction_id = req.transaction_id
    data = json.loads(req.data) if req.data else None

    if transaction_type == 'supplier_edit':
        supplier = db.session.get(Supplier, transaction_id)
        if supplier and data:
            supplier.name = data.get('name', supplier.name)
            supplier.phone = data.get('phone', supplier.phone)
            supplier.email = data.get('email', supplier.email)
            supplier.address = data.get('address', supplier.address)
            supplier.bank_name = data.get('bank_name', supplier.bank_name)
            supplier.bank_branch = data.get('bank_branch', supplier.bank_branch)
            supplier.bank_account_number = data.get('bank_account_number', supplier.bank_account_number)
            supplier.payment_terms = data.get('payment_terms', supplier.payment_terms)
            db.session.commit()

    elif transaction_type == 'supplier_delete':
        supplier = db.session.get(Supplier, transaction_id)
        if supplier:
            supplier.is_active = False
            db.session.commit()

    elif transaction_type == 'customer_edit':
        customer = db.session.get(Customer, transaction_id)
        if customer and data:
            customer.name = data.get('name', customer.name)
            customer.phone = data.get('phone', customer.phone)
            customer.email = data.get('email', customer.email)
            customer.address = data.get('address', customer.address)
            customer.bank_name = data.get('bank_name', customer.bank_name)
            customer.bank_branch = data.get('bank_branch', customer.bank_branch)
            customer.bank_account_number = data.get('bank_account_number', customer.bank_account_number)
            db.session.commit()

    elif transaction_type == 'customer_delete':
        customer = db.session.get(Customer, transaction_id)
        if customer:
            customer.is_active = False
            db.session.commit()

    elif transaction_type == 'payment':
        # When a payment is fully approved, post the accounting entries
        from models import Payment, FinancialCategory, LineItem
        payment = db.session.get(Payment, transaction_id)
        if payment:
            payment.status = 'approved'
            from services.fifo_service import _post_payment_accounting
            _post_payment_accounting(
                payment_date=payment.payment_date,
                amount=float(payment.amount),
                payment_id=payment.id,
                business_id=payment.business_id,
                created_by=payment.created_by or req.created_by,
                category_id=payment.category_id,
                line_item_id=payment.line_item_id,
                payee_type=payment.payee_type,
            )
            db.session.commit()

    elif transaction_type == 'journal_entry':
        # When a manual journal entry is fully approved, post the balanced
        # double-entry record.
        proposal = json.loads(req.data) if req.data else {}
        lines = proposal.get('lines', [])
        description = proposal.get('description', 'Journal entry')
        entry_date_str = proposal.get('entry_date')
        entry_date = datetime.fromisoformat(entry_date_str) if entry_date_str else datetime.now(timezone.utc)
        accounting_lines = [
            {
                'account_id': l['account_id'],
                'debit_amount': l['debit_amount'],
                'credit_amount': l['credit_amount'],
            }
            for l in lines
        ]
        from app.services.accounting_service import post_entry as _post_entry
        _post_entry(
            req.business_id,
            entry_date,
            description,
            accounting_lines,
            reference_type='JournalEntry',
            created_by=req.created_by,
        )
        db.session.commit()


from . import approvals_bp  # noqa: E402, F811