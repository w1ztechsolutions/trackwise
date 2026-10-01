"""Accounting blueprint: Chart of Accounts management and manual journal entries.

Follows the project's double-entry conventions:
- All queries are scoped to ``current_user.business_id``.
- Posting always goes through ``accounting_service.post_entry`` (atomic JE + audit log).
- Manual journal entries are approval-gated when a workflow is configured for the
  ``journal_entry`` transaction type (see ``approvals._execute_approval``).
"""

import json
from datetime import date, datetime, timedelta, timezone

from flask import (
    abort, flash, jsonify, redirect, render_template, request, url_for,
)
from sqlalchemy.exc import IntegrityError

from app.accounting.coa_taxonomy import build_coa_tree, COA_TAXONOMY
from flask_login import current_user, login_required

from models import db
from app.models import Invoice, Sale
from app.models.accounting import (
    Business,
    Branch,
    CostCenter,
    ChartOfAccounts,
    JournalEntry,
    JournalLine,
    BankStatement,
    RevenueRecognitionSchedule,
)
from app.models.approval import ApprovalConfig, ApprovalRequest
from app.services.accounting_service import (
    AccountingException, post_entry, post_opening_balance, reverse_entry,
    verify_balances,
)
from app.services.period_service import close_period, reopen_period
from app.services.revenue_recognition_service import (
    RevenueRecognitionError,
    create_revenue_schedule,
    recognize_revenue,
)
from app.auth.decorators import role_required
from app.services.approval_service import create_approval_request

from . import accounting_bp


ACCOUNT_TYPES = [
    ('asset', 'Asset'),
    ('liability', 'Liability'),
    ('equity', 'Equity'),
    ('income', 'Income'),
    ('expense', 'Expense'),
]


def _biz_id():
    bid = getattr(current_user, 'business_id', None)
    if not bid:
        abort(404)
    return bid


def _accounts_for_select(business_id):
    accounts = (
        ChartOfAccounts.query
        .filter_by(business_id=business_id, is_active=True)
        .order_by(ChartOfAccounts.code)
        .all()
    )
    return [{'id': a.id, 'code': a.code, 'name': a.name, 'type': a.type} for a in accounts]


def _active_dimensions(model, business_id):
    return (
        model.query.filter_by(business_id=business_id, is_active=True)
        .order_by(model.code)
        .all()
    )


@accounting_bp.route('/accounting/dimensions', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'accountant')
def dimensions():
    biz_id = _biz_id()
    if request.method == 'POST':
        dimension_type = request.form.get('dimension_type', '')
        dimension_model = {
            'branch': Branch,
            'cost_center': CostCenter,
        }.get(dimension_type)
        code = request.form.get('code', '').strip()
        name = request.form.get('name', '').strip()
        if dimension_model is None:
            abort(400)
        if not code or not name:
            flash('A code and name are required.', 'danger')
        elif len(code) > 20 or len(name) > 200:
            flash('Codes must be at most 20 characters and names at most 200 characters.', 'danger')
        elif dimension_model.query.filter_by(
            business_id=biz_id, code=code
        ).first():
            flash(f'The {dimension_type.replace("_", " ")} code already exists.', 'danger')
        else:
            db.session.add(dimension_model(
                business_id=biz_id,
                code=code,
                name=name,
                is_active=True,
            ))
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash('That code is already in use.', 'danger')
            else:
                flash(f'{dimension_type.replace("_", " ").title()} created.', 'success')
                return redirect(url_for('accounting.dimensions'))

    return render_template(
        'accounting_dimensions.html',
        branches=Branch.query.filter_by(business_id=biz_id).order_by(Branch.code).all(),
        cost_centers=CostCenter.query.filter_by(
            business_id=biz_id
        ).order_by(CostCenter.code).all(),
    )


@accounting_bp.route(
    '/accounting/dimensions/<dimension_type>/<int:dimension_id>/toggle',
    methods=['POST'],
)
@login_required
@role_required('admin', 'accountant')
def dimension_toggle(dimension_type, dimension_id):
    biz_id = _biz_id()
    dimension_model = {
        'branch': Branch,
        'cost-center': CostCenter,
    }.get(dimension_type)
    if dimension_model is None:
        abort(404)
    dimension = dimension_model.query.filter_by(
        id=dimension_id,
        business_id=biz_id,
    ).first_or_404()
    dimension.is_active = not dimension.is_active
    db.session.commit()
    flash(
        f'{dimension_type.replace("-", " ").title()} '
        f'{"activated" if dimension.is_active else "archived"}.',
        'success',
    )
    return redirect(url_for('accounting.dimensions'))


# ─── Chart of Accounts ────────────────────────────────────────────────────

@accounting_bp.route('/accounting/chart-of-accounts')
@login_required
@role_required('admin', 'accountant')
def coa_list():
    biz_id = _biz_id()
    accounts = (
        ChartOfAccounts.query.filter_by(business_id=biz_id)
        .order_by(ChartOfAccounts.code)
        .all()
    )
    parents = _accounts_for_select(biz_id)
    parent_map = {a['id']: a['name'] for a in parents}
    parent_map.update({a['id']: f"{a['code']} — {a['name']}" for a in parents})
    return render_template(
        'chart_of_accounts.html',
        accounts=accounts,
        ACCOUNT_TYPES=ACCOUNT_TYPES,
        parents=parents,
        parent_map=parent_map,
        taxonomy=COA_TAXONOMY,
    )


@accounting_bp.route('/accounting/chart-of-accounts/create', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'accountant')
def coa_create():
    biz_id = _biz_id()
    parents = _accounts_for_select(biz_id)
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        name = request.form.get('name', '').strip()
        type_ = request.form.get('type', 'expense')
        parent_id_raw = request.form.get('parent_id', '').strip()

        if not code or not name:
            flash('Account code and name are required.', 'danger')
            return redirect(url_for('accounting.coa_create'))
        if type_ not in [t for t, _ in ACCOUNT_TYPES]:
            flash('Invalid account type.', 'danger')
            return redirect(url_for('accounting.coa_create'))

        if ChartOfAccounts.query.filter_by(business_id=biz_id, code=code).first():
            flash(f'An account with code "{code}" already exists.', 'danger')
            return redirect(url_for('accounting.coa_create'))

        try:
            parent_id = int(parent_id_raw) if parent_id_raw else None
        except ValueError:
            parent_id = None
        if parent_id:
            parent = db.session.get(ChartOfAccounts, parent_id)
            if not parent or parent.business_id != biz_id:
                flash('Invalid parent account.', 'danger')
                return redirect(url_for('accounting.coa_create'))

        account = ChartOfAccounts(
            business_id=biz_id, code=code, name=name, type=type_,
            parent_id=parent_id, is_active=True,
        )
        db.session.add(account)
        db.session.commit()
        flash(f'Account {code} – {name} created.', 'success')
        return redirect(url_for('accounting.coa_list'))

    return redirect(url_for('accounting.coa_list'))


@accounting_bp.route('/accounting/chart-of-accounts/<int:account_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'accountant')
def coa_edit(account_id):
    biz_id = _biz_id()
    account = db.session.get(ChartOfAccounts, account_id)
    if not account or account.business_id != biz_id:
        abort(404)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        type_ = request.form.get('type', account.type)
        parent_id_raw = request.form.get('parent_id', '').strip()
        is_active = request.form.get('is_active', 'on') == 'on'

        if not name:
            flash('Account name is required.', 'danger')
            return redirect(url_for('accounting.coa_edit', account_id=account_id))
        if type_ not in [t for t, _ in ACCOUNT_TYPES]:
            type_ = account.type

        existing = ChartOfAccounts.query.filter_by(
            business_id=biz_id, code=account.code
        ).first()
        if existing and existing.id != account.id:
            flash(f'Another account already uses code "{account.code}".', 'danger')
            return redirect(url_for('accounting.coa_edit', account_id=account_id))

        try:
            parent_id = int(parent_id_raw) if parent_id_raw else None
        except ValueError:
            parent_id = None
        if parent_id:
            parent = db.session.get(ChartOfAccounts, parent_id)
            if not parent or parent.business_id != biz_id or parent.id == account.id:
                flash('Invalid parent account.', 'danger')
                return redirect(url_for('accounting.coa_edit', account_id=account_id))
        account.parent_id = parent_id

        account.name = name
        account.type = type_
        account.is_active = is_active
        db.session.commit()
        flash(f'Account {account.code} updated.', 'success')
        return redirect(url_for('accounting.coa_list'))

    return redirect(url_for('accounting.coa_list'))


@accounting_bp.route('/accounting/chart-of-accounts/<int:account_id>/archive', methods=['POST'])
@login_required
@role_required('admin', 'accountant')
def coa_archive(account_id):
    biz_id = _biz_id()
    account = db.session.get(ChartOfAccounts, account_id)
    if not account or account.business_id != biz_id:
        abort(404)
    account.is_active = False
    db.session.commit()
    flash(f'Account {account.code} archived.', 'success')
    return redirect(url_for('accounting.coa_list'))


@accounting_bp.route('/accounting/chart-of-accounts/<int:account_id>/restore', methods=['POST'])
@login_required
@role_required('admin', 'accountant')
def coa_restore(account_id):
    biz_id = _biz_id()
    account = db.session.get(ChartOfAccounts, account_id)
    if not account or account.business_id != biz_id:
        abort(404)
    account.is_active = True
    db.session.commit()
    flash(f'Account {account.code} restored.', 'success')
    return redirect(url_for('accounting.coa_list'))


@accounting_bp.route('/accounting/chart-of-accounts/<int:account_id>/opening-balance', methods=['POST'])
@login_required
@role_required('admin', 'accountant')
def coa_opening_balance(account_id):
    biz_id = _biz_id()
    account = db.session.get(ChartOfAccounts, account_id)
    if not account or account.business_id != biz_id:
        abort(404)
    amount_raw = request.form.get('amount', '').strip()
    try:
        amount = float(amount_raw)
    except (TypeError, ValueError):
        flash('Opening balance must be a valid number.', 'danger')
        return redirect(url_for('accounting.coa_list'))
    try:
        post_opening_balance(biz_id, account.id, amount, created_by=current_user.id)
        db.session.commit()
        flash(f'Opening balance of {amount} posted to {account.code} – {account.name}.', 'success')
    except AccountingException as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('accounting.coa_list'))


# ─── Manual Journal Entries ───────────────────────────────────────────────

@accounting_bp.route('/accounting/journal-entries')
@login_required
@role_required('admin', 'accountant')
def je_list():
    biz_id = _biz_id()
    entries = (
        JournalEntry.query
        .filter_by(business_id=biz_id, reference_type='JournalEntry')
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc())
        .all()
    )
    jes_account_ids = {l.account_id for e in entries for l in e.lines}
    account_map = {
        a.id: f"{a.code} — {a.name}"
        for a in ChartOfAccounts.query.filter(
            ChartOfAccounts.business_id == biz_id,
            ChartOfAccounts.id.in_(jes_account_ids),
        ).all()
    }
    return render_template('journal_entries.html', entries=entries, account_map=account_map)


@accounting_bp.route('/accounting/journal-entries/create', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'accountant')
def je_create():
    biz_id = _biz_id()

    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        entry_date_raw = request.form.get('entry_date') or datetime.now(timezone.utc).date().isoformat()
        try:
            entry_date = datetime.fromisoformat(entry_date_raw)
        except ValueError:
            flash('Enter a valid journal entry date.', 'danger')
            return redirect(url_for('accounting.je_create'))
        account_ids = request.form.getlist('account_id')
        debits = request.form.getlist('debit_amount')
        credits = request.form.getlist('credit_amount')
        cost_center_ids = request.form.getlist('cost_center_id')
        if not cost_center_ids:
            cost_center_ids = [''] * len(account_ids)
        branch_id_raw = request.form.get('branch_id', '').strip()
        try:
            branch_id = int(branch_id_raw) if branch_id_raw else None
        except ValueError:
            branch_id = -1
        if branch_id is not None and not Branch.query.filter_by(
            id=branch_id,
            business_id=biz_id,
            is_active=True,
        ).first():
            flash('Selected branch is not valid for this business.', 'danger')
            return redirect(url_for('accounting.je_create'))

        parsed_lines = []
        errors = []
        for acc_id_raw, debit_raw, credit_raw, cost_center_id_raw in zip(
            account_ids, debits, credits, cost_center_ids
        ):
            acc_id_raw = acc_id_raw.strip() if acc_id_raw else ''
            if not acc_id_raw:
                continue
            try:
                acc_id = int(acc_id_raw)
            except ValueError:
                errors.append(f'Invalid account selection.')
                continue
            account = db.session.get(ChartOfAccounts, acc_id)
            if not account or account.business_id != biz_id or not account.is_active:
                errors.append(f'Selected account is not valid for this business.')
                continue
            try:
                debit = float(debit_raw or 0)
                credit = float(credit_raw or 0)
            except ValueError:
                errors.append('Amounts must be numeric.')
                continue
            if debit < 0 or credit < 0:
                errors.append('Line amounts cannot be negative.')
                continue
            if debit > 0 and credit > 0:
                errors.append('A line cannot be both a debit and a credit.')
                continue
            cost_center_id_raw = (cost_center_id_raw or '').strip()
            try:
                cost_center_id = int(cost_center_id_raw) if cost_center_id_raw else None
            except ValueError:
                errors.append('Invalid cost center selection.')
                continue
            if cost_center_id is not None and not CostCenter.query.filter_by(
                id=cost_center_id,
                business_id=biz_id,
                is_active=True,
            ).first():
                errors.append('Selected cost center is not valid for this business.')
                continue
            parsed_lines.append({
                'account_id': account.id,
                'account_code': account.code,
                'account_name': account.name,
                'debit_amount': round(debit, 2),
                'credit_amount': round(credit, 2),
                'cost_center_id': cost_center_id,
            })

        if not description:
            errors.append('A description is required.')
        if len(parsed_lines) < 2:
            errors.append('Journal entries require at least two lines.')

        total_debit = sum(l['debit_amount'] for l in parsed_lines)
        total_credit = sum(l['credit_amount'] for l in parsed_lines)
        if abs(total_debit - total_credit) > 0.01:
            errors.append(
                f'Entry does not balance: debits={total_debit:.2f}, credits={total_credit:.2f}.'
            )

        if errors:
            for err in errors:
                flash(err, 'danger')
            return redirect(url_for('accounting.je_create'))

        proposal = {
            'description': description,
            'entry_date': entry_date_raw,
            'branch_id': branch_id,
            'lines': parsed_lines,
        }

        config = ApprovalConfig.query.filter_by(
            business_id=biz_id, transaction_type='journal_entry', is_active=True
        ).first()

        if config:
            req = create_approval_request(
                business_id=biz_id,
                transaction_type='journal_entry',
                transaction_id=0,
                created_by=current_user.id,
            )
            req.data = json.dumps(proposal)
            db.session.commit()
            flash('Journal entry submitted for approval.', 'success')
        else:
            try:
                entry = post_entry(
                    biz_id,
                    entry_date,
                    description,
                    [
                        {'account_id': l['account_id'],
                         'debit_amount': l['debit_amount'],
                         'credit_amount': l['credit_amount'],
                         'cost_center_id': l['cost_center_id']}
                        for l in parsed_lines
                    ],
                    reference_type='JournalEntry',
                    created_by=current_user.id,
                    branch_id=branch_id,
                )
                db.session.commit()
                flash(f'Journal entry #{entry.id} posted.', 'success')
            except AccountingException as e:
                db.session.rollback()
                flash(str(e), 'danger')
                return redirect(url_for('accounting.je_create'))

        return redirect(url_for('accounting.je_list'))

    accounts = _accounts_for_select(biz_id)
    branches = _active_dimensions(Branch, biz_id)
    cost_centers = _active_dimensions(CostCenter, biz_id)
    today = datetime.now(timezone.utc).date().isoformat()
    return render_template(
        'journal_entry_form.html',
        accounts=accounts,
        branches=branches,
        cost_centers=cost_centers,
        today=today,
    )


@accounting_bp.route('/accounting/journal-entries/<int:entry_id>')
@login_required
@role_required('admin', 'accountant')
def je_view(entry_id):
    biz_id = _biz_id()
    entry = db.session.get(JournalEntry, entry_id)
    if not entry or entry.business_id != biz_id:
        abort(404)
    account_ids = {l.account_id for l in entry.lines}
    account_map = {
        a.id: f"{a.code} — {a.name}"
        for a in ChartOfAccounts.query.filter(
            ChartOfAccounts.business_id == biz_id,
            ChartOfAccounts.id.in_(account_ids),
        ).all()
    }
    total_debit = sum(float(line.debit_amount or 0) for line in entry.lines)
    total_credit = sum(float(line.credit_amount or 0) for line in entry.lines)
    return render_template(
        'journal_entry_view.html',
        entry=entry,
        account_map=account_map,
        reversal_entry=entry.reversal_entry,
        total_debit=total_debit,
        total_credit=total_credit,
    )


@accounting_bp.route('/accounting/journal-entries/<int:entry_id>/reverse', methods=['POST'])
@login_required
@role_required('admin', 'accountant')
def je_reverse(entry_id):
    biz_id = _biz_id()
    reason = request.form.get('reason', '').strip()
    try:
        reversal = reverse_entry(
            biz_id,
            entry_id,
            reason,
            created_by=current_user.id,
        )
    except AccountingException as error:
        db.session.rollback()
        flash(str(error), 'danger')
        return redirect(url_for('accounting.je_view', entry_id=entry_id))

    flash(f'Journal entry reversed with entry #{reversal.id}. The original remains in the ledger.', 'success')
    return redirect(url_for('accounting.je_view', entry_id=entry_id))


@accounting_bp.route('/accounting/period-close', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'accountant')
def period_close():
    biz_id = _biz_id()
    business = db.session.get(Business, biz_id)

    if request.method == 'POST':
        close_date_raw = request.form.get('close_through', '').strip()
        try:
            close_through = date.fromisoformat(close_date_raw)
            close_period(biz_id, close_through)
            db.session.commit()
        except ValueError as error:
            db.session.rollback()
            flash(str(error) or 'Enter a valid close-through date.', 'danger')
            return redirect(url_for('accounting.period_close'))

        flash(f'Accounting period is now closed through {close_through.isoformat()}.', 'success')
        return redirect(url_for('accounting.period_close'))

    return render_template(
        'period_close.html',
        last_closed_period_date=business.last_closed_period_date,
        can_reopen_period=current_user.role == 'admin',
        today=date.today().isoformat(),
        min_close_date=(
            (business.last_closed_period_date + timedelta(days=1)).isoformat()
            if business.last_closed_period_date else ''
        ),
    )


@accounting_bp.route('/accounting/period-close/reopen', methods=['POST'])
@login_required
@role_required('admin')
def period_reopen():
    biz_id = _biz_id()
    if request.form.get('confirm_reopen') != 'yes':
        flash('Confirm that you want to reopen the closed period.', 'danger')
        return redirect(url_for('accounting.period_close'))

    try:
        reopened_through = reopen_period(biz_id)
        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        flash(str(error), 'danger')
        return redirect(url_for('accounting.period_close'))

    flash(
        f'Accounting period closed through {reopened_through.isoformat()} has been reopened.',
        'success',
    )
    return redirect(url_for('accounting.period_close'))


@accounting_bp.route('/accounting/revenue-recognition', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'accountant')
def revenue_recognition():
    biz_id = _biz_id()
    if request.method == 'POST':
        try:
            schedule = create_revenue_schedule(
                business_id=biz_id,
                invoice_id=int(request.form.get('invoice_id', '')),
                revenue_account_id=int(request.form.get('revenue_account_id', '')),
                deferred_revenue_account_id=int(
                    request.form.get('deferred_revenue_account_id', '')
                ),
                amount=request.form.get('amount', ''),
                start_date=date.fromisoformat(request.form.get('start_date', '')),
                end_date=date.fromisoformat(request.form.get('end_date', '')),
                created_by=current_user.id,
            )
        except (ValueError, TypeError) as error:
            db.session.rollback()
            flash(str(error) or 'Enter valid schedule details.', 'danger')
            return redirect(url_for('accounting.revenue_recognition'))

        flash(f'Revenue schedule #{schedule.id} created and the amount deferred.', 'success')
        return redirect(url_for('accounting.revenue_recognition'))

    posted_invoice_ids = (
        db.session.query(Sale.invoice_id)
        .join(
            JournalEntry,
            (JournalEntry.reference_id == Sale.id)
            & (JournalEntry.reference_type == 'Sale'),
        )
        .filter(
            Sale.business_id == biz_id,
            Sale.invoice_id.isnot(None),
            JournalEntry.business_id == biz_id,
            JournalEntry.is_deleted.is_(False),
        )
        .distinct()
        .all()
    )
    scheduled_invoice_ids = db.session.query(
        RevenueRecognitionSchedule.invoice_id
    ).filter_by(business_id=biz_id)
    eligible_invoices = Invoice.query.filter(
        Invoice.business_id == biz_id,
        Invoice.status.notin_(('draft', 'void')),
        Invoice.id.in_([row[0] for row in posted_invoice_ids]),
        ~Invoice.id.in_(scheduled_invoice_ids),
    ).order_by(Invoice.invoice_date.desc()).all()
    income_accounts = ChartOfAccounts.query.filter_by(
        business_id=biz_id,
        type='income',
        is_active=True,
    ).order_by(ChartOfAccounts.code).all()
    liability_accounts = ChartOfAccounts.query.filter_by(
        business_id=biz_id,
        type='liability',
        is_active=True,
    ).order_by(ChartOfAccounts.code).all()
    schedules = RevenueRecognitionSchedule.query.filter_by(
        business_id=biz_id,
    ).order_by(RevenueRecognitionSchedule.start_date.desc()).all()
    return render_template(
        'revenue_recognition.html',
        invoices=eligible_invoices,
        income_accounts=income_accounts,
        liability_accounts=liability_accounts,
        schedules=schedules,
        today=date.today().isoformat(),
    )


@accounting_bp.route(
    '/accounting/revenue-recognition/<int:schedule_id>/recognize',
    methods=['POST'],
)
@login_required
@role_required('admin', 'accountant')
def revenue_recognition_post(schedule_id):
    biz_id = _biz_id()
    try:
        through_date = date.fromisoformat(
            request.form.get('through_date', '').strip()
        )
        entry = recognize_revenue(
            schedule_id,
            biz_id,
            through_date,
            created_by=current_user.id,
        )
    except (RevenueRecognitionError, ValueError) as error:
        db.session.rollback()
        flash(str(error) or 'Enter a valid recognition date.', 'danger')
        return redirect(url_for('accounting.revenue_recognition'))

    if entry is None:
        flash('No additional revenue was due for recognition on that date.', 'info')
    else:
        flash(f'Revenue recognition posted as journal entry #{entry.id}.', 'success')
    return redirect(url_for('accounting.revenue_recognition'))


# ─── Bank Reconciliation ────────────────────────────────────────────────────

BANK_ACCOUNT_CODES = ('1000', '1100')


def _bank_accounts(business_id):
    return (
        ChartOfAccounts.query
        .filter(
            ChartOfAccounts.business_id == business_id,
            ChartOfAccounts.is_active == True,
            ChartOfAccounts.code.in_(BANK_ACCOUNT_CODES),
        )
        .order_by(ChartOfAccounts.code)
        .all()
    )


@accounting_bp.route('/accounting/bank-reconciliation')
@login_required
@role_required('admin', 'accountant')
def bank_recon():
    biz_id = _biz_id()
    accounts = _bank_accounts(biz_id)
    for acct in accounts:
        acct.unreconciled_count = BankStatement.query.filter_by(
            business_id=biz_id, account_id=acct.id, is_reconciled=False
        ).count()
    return render_template('bank_reconciliation.html', accounts=accounts)


@accounting_bp.route('/accounting/bank-reconciliation/register/<int:account_id>')
@login_required
@role_required('admin', 'accountant')
def bank_register(account_id):
    biz_id = _biz_id()
    account = db.session.get(ChartOfAccounts, account_id)
    if not account or account.business_id != biz_id:
        abort(404)

    page = request.args.get('page', 1, type=int)
    per_page = min(max(request.args.get('per_page', 25, type=int), 10), 100)

    entries = (
        JournalEntry.query
        .join(JournalLine)
        .filter(
            JournalEntry.business_id == biz_id,
            JournalLine.account_id == account_id,
        )
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc())
        .paginate(page=page, per_page=per_page)
    )

    lines_data = []
    for entry in entries.items:
        for line in entry.lines:
            if line.account_id == account_id:
                debit = float(line.debit_amount)
                credit = float(line.credit_amount)
                amount = debit - credit
                lines_data.append({
                    'date': entry.entry_date,
                    'description': entry.description,
                    'reference_type': entry.reference_type,
                    'debit': debit if amount > 0 else 0,
                    'credit': credit if amount < 0 else 0,
                    'amount': amount,
                    'entry_id': entry.id,
                })

    total_debits = sum(l['debit'] for l in lines_data)
    total_credits = sum(l['credit'] for l in lines_data)

    return render_template(
        'bank_register.html',
        account=account,
        lines=lines_data,
        total_debits=total_debits,
        total_credits=total_credits,
        page=page,
        per_page=per_page,
        pages=entries.pages,
        total=entries.total,
    )


@accounting_bp.route('/accounting/bank-reconciliation/statements/<int:account_id>')
@login_required
@role_required('admin', 'accountant')
def bank_statements(account_id):
    biz_id = _biz_id()
    account = db.session.get(ChartOfAccounts, account_id)
    if not account or account.business_id != biz_id:
        abort(404)

    page = request.args.get('page', 1, type=int)
    per_page = min(max(request.args.get('per_page', 25, type=int), 10), 100)

    stmts = (
        BankStatement.query
        .filter_by(business_id=biz_id, account_id=account_id)
        .order_by(BankStatement.statement_date.desc(), BankStatement.id.desc())
        .paginate(page=page, per_page=per_page)
    )

    return render_template('bank_statements.html', account=account, statements=stmts)


@accounting_bp.route('/accounting/bank-reconciliation/import', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'accountant')
def bank_statement_import():
    biz_id = _biz_id()
    accounts = _bank_accounts(biz_id)

    if request.method == 'POST':
        account_id = request.form.get('account_id', '').strip()
        csv_text = request.form.get('csv_data', '').strip()

        if not account_id:
            flash('Please select a bank account.', 'danger')
            return redirect(url_for('accounting.bank_statement_import'))

        try:
            account_id = int(account_id)
        except ValueError:
            flash('Invalid bank account selection.', 'danger')
            return redirect(url_for('accounting.bank_statement_import'))

        account = db.session.get(ChartOfAccounts, account_id)
        if not account or account.business_id != biz_id:
            abort(404)

        if not csv_text:
            flash('Please paste CSV statement data.', 'danger')
            return redirect(url_for('accounting.bank_statement_import'))

        imported = 0
        errors = 0

        for line in csv_text.strip().splitlines():
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 3:
                errors += 1
                continue
            try:
                stmt_date = datetime.fromisoformat(parts[0])
            except (ValueError, TypeError):
                try:
                    stmt_date = datetime.strptime(parts[0], '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    try:
                        stmt_date = datetime.strptime(parts[0], '%Y-%m-%d')
                    except (ValueError, TypeError):
                        errors += 1
                        continue

            try:
                amount = float(parts[1])
            except ValueError:
                errors += 1
                continue

            description = parts[2] if len(parts) > 2 else ''
            reference = parts[3] if len(parts) > 3 else None

            stmt = BankStatement(
                business_id=biz_id,
                account_id=account_id,
                statement_date=stmt_date,
                description=description,
                amount=amount,
                reference=reference,
            )
            db.session.add(stmt)
            imported += 1

        db.session.commit()
        flash(f'Imported {imported} statement lines ({errors} errors).', 'success')
        return redirect(url_for('accounting.bank_statements', account_id=account_id))

    return render_template('bank_statement_import.html', accounts=accounts)


@accounting_bp.route('/accounting/bank-reconciliation/statements/<int:account_id>/reconcile')
@login_required
@role_required('admin', 'accountant')
def bank_reconcile(account_id):
    biz_id = _biz_id()
    account = db.session.get(ChartOfAccounts, account_id)
    if not account or account.business_id != biz_id:
        abort(404)

    page = request.args.get('page', 1, type=int)
    per_page = min(max(request.args.get('per_page', 25, type=int), 10), 100)
    show = request.args.get('show', 'unreconciled')

    query = (
        BankStatement.query
        .filter_by(business_id=biz_id, account_id=account_id)
        .order_by(BankStatement.statement_date.desc(), BankStatement.id.desc())
    )

    if show == 'unreconciled':
        query = query.filter_by(is_reconciled=False)
    elif show == 'reconciled':
        query = query.filter_by(is_reconciled=True)

    stmts = query.paginate(page=page, per_page=per_page)

    suggestions = {}
    for stmt in stmts.items:
        if not stmt.is_reconciled:
            abs_amount = abs(float(stmt.amount))
            candidates = (
                JournalEntry.query
                .join(JournalLine)
                .filter(
                    JournalEntry.business_id == biz_id,
                    JournalLine.account_id == account_id,
                    JournalEntry.entry_date >= stmt.statement_date - timedelta(hours=48),
                    JournalEntry.entry_date <= stmt.statement_date + timedelta(hours=48),
                )
                .order_by(JournalEntry.entry_date.asc())
                .all()
            )
            suggestions[stmt.id] = [
                {
                    'entry_id': e.id,
                    'date': e.entry_date,
                    'description': e.description,
                    'amount': abs(sum(float(l.debit_amount) - float(l.credit_amount) for l in e.lines if l.account_id == account_id)),
                }
                for e in candidates
            ]

    return render_template(
        'bank_reconcile.html',
        account=account,
        statements=stmts,
        suggestions=suggestions,
        show=show,
        page=page,
        per_page=per_page,
    )


@accounting_bp.route('/accounting/bank-reconciliation/match', methods=['POST'])
@login_required
@role_required('admin', 'accountant')
def bank_match():
    biz_id = _biz_id()
    statement_id = request.form.get('statement_id', '').strip()
    entry_id = request.form.get('entry_id', '').strip()

    if not statement_id or not entry_id:
        flash('Invalid match request.', 'danger')
        return redirect(url_for('accounting.bank_recon'))

    stmt = db.session.get(BankStatement, int(statement_id))
    if not stmt or stmt.business_id != biz_id:
        abort(404)

    entry = db.session.get(JournalEntry, int(entry_id))
    if not entry or entry.business_id != biz_id:
        abort(404)

    stmt.is_reconciled = True
    stmt.journal_entry_id = entry.id
    db.session.commit()
    flash('Statement line matched to journal entry.', 'success')
    return redirect(url_for('accounting.bank_reconcile', account_id=stmt.account_id))


@accounting_bp.route('/accounting/bank-reconciliation/unmatch', methods=['POST'])
@login_required
@role_required('admin', 'accountant')
def bank_unmatch():
    biz_id = _biz_id()
    statement_id = request.form.get('statement_id', '').strip()

    stmt = db.session.get(BankStatement, int(statement_id))
    if not stmt or stmt.business_id != biz_id:
        abort(404)

    stmt.is_reconciled = False
    stmt.journal_entry_id = None
    db.session.commit()
    flash('Statement line unmatched.', 'info')
    return redirect(url_for('accounting.bank_reconcile', account_id=stmt.account_id))


@accounting_bp.route('/accounting/bank-reconciliation/unreconciled')
@login_required
@role_required('admin', 'accountant')
def bank_unreconciled_report():
    biz_id = _biz_id()
    accounts = _bank_accounts(biz_id)

    report = []
    for acct in accounts:
        stmts = (
            BankStatement.query
            .filter_by(business_id=biz_id, account_id=acct.id, is_reconciled=False)
            .order_by(BankStatement.statement_date.desc())
            .all()
        )
        total = sum(float(s.amount) for s in stmts)
        report.append({
            'account': acct,
            'unreconciled_count': len(stmts),
            'unreconciled_amount': total,
            'statements': stmts[:5],
        })

    total_unreconciled = sum(r['unreconciled_amount'] for r in report)

    return render_template(
        'bank_unreconciled.html',
        accounts=report,
        total_unreconciled=total_unreconciled,
    )


@accounting_bp.route('/accounting/chart-of-accounts/seed', methods=['GET'])
@login_required
@role_required('admin', 'accountant')
def coa_seeder():
    return render_template('coa_seeder_modal.html', taxonomy=COA_TAXONOMY)


@accounting_bp.route('/accounting/chart-of-accounts/seed', methods=['POST'])
@login_required
@role_required('admin', 'accountant')
def coa_seeder_import():
    biz_id = _biz_id()
    payload = request.get_json(silent=True) or {}
    selected_codes = payload.get('selected_codes', [])
    if not selected_codes:
        return jsonify({'imported': 0, 'skipped': 0, 'skipped_codes': [], 'message': 'No accounts selected.'})

    tree = build_coa_tree(selected_codes)
    existing_codes = {
        row[0] for row in
        ChartOfAccounts.query.with_entities(ChartOfAccounts.code)
        .filter_by(business_id=biz_id).all()
    }
    code_map = {row[0]: row[1] for row in
        ChartOfAccounts.query.with_entities(ChartOfAccounts.code, ChartOfAccounts.id)
        .filter_by(business_id=biz_id).all()
    }

    subtotals_to_insert = []
    leaves_to_insert = []
    skipped = []
    imported = 0

    for acct in tree:
        if acct['code'] in existing_codes:
            skipped.append(acct['code'])
            continue
        if acct.get('is_subtotal'):
            subtotals_to_insert.append(acct)
        else:
            leaves_to_insert.append(acct)

    inserted = {}
    for acct in subtotals_to_insert:
        parent_id = None
        if acct.get('parent_code'):
            parent_id = inserted.get(acct['parent_code']) or code_map.get(acct['parent_code'])
        record = ChartOfAccounts(
            business_id=biz_id,
            code=acct['code'],
            name=acct['name'],
            type=acct['type'],
            is_active=True,
            parent_id=parent_id,
        )
        db.session.add(record)
        inserted[acct['code']] = record.id

    db.session.flush()

    for acct in leaves_to_insert:
        parent_id = None
        if acct.get('parent_code'):
            parent_id = inserted.get(acct['parent_code']) or code_map.get(acct['parent_code'])
        record = ChartOfAccounts(
            business_id=biz_id,
            code=acct['code'],
            name=acct['name'],
            type=acct['type'],
            is_active=True,
            parent_id=parent_id,
        )
        db.session.add(record)
        imported += 1

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'imported': 0, 'skipped': len(skipped) + imported, 'skipped_codes': skipped, 'message': 'A duplicate was detected during import. No accounts were added.'}), 409

    total_skipped = len(skipped) + (len(leaves_to_insert) - imported)
    if imported > 0:
        message = f"Imported {imported} accounts. {total_skipped} skipped (already exist)."
    else:
        message = f"No new accounts imported. {total_skipped} skipped (already exist)."
    return jsonify({'imported': imported, 'skipped': total_skipped, 'skipped_codes': skipped, 'message': message})
