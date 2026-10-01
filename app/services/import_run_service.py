"""Lifecycle for staged spreadsheet imports (ADR-0013).

An import runs in two steps: the upload step parses the workbook and stages the
parsed rows against an ``ImportRun`` row; the mapping step loads that staged run,
imports the rows, and closes the run. Staged row contents are purged when the run
completes, so only counts and the rejected-row list are retained.
"""

import json
from datetime import datetime, timedelta, timezone

from flask import abort, flash, url_for

from app.models import ImportRun, db
from app.services.audit_service import record_user_action


STAGED_STATUS = 'staged'
COMMITTED_STATUS = 'committed'
FAILED_STATUS = 'failed'

VALID_DATE_ORDERS = {'MDY', 'DMY'}

MAX_FLASHED_ERRORS = 10


def normalize_date_order(value):
    """Return ``'MDY'`` or ``'DMY'``; anything else resolves to ``'MDY'``."""
    order = str(value or '').strip().upper()
    return order if order in VALID_DATE_ORDERS else 'MDY'


def stage_import(
    business_id,
    user_id,
    entity,
    filename,
    rows,
    column_map=None,
    date_order='MDY',
    account_id=None,
):
    """Persist parsed rows against a new ``staged`` import run."""
    run = ImportRun(
        business_id=business_id,
        user_id=user_id,
        entity=entity,
        filename=filename,
        status=STAGED_STATUS,
        column_map=json.dumps(column_map or {}, sort_keys=True),
        date_order=normalize_date_order(date_order),
        account_id=account_id,
        row_count=len(rows),
        staged_rows=json.dumps(rows, default=str),
    )
    db.session.add(run)
    return run


def load_staged(business_id, run_id):
    """Return the caller's staged run, or abort with 404.

    Tenant scope is enforced here: a staged run belongs to exactly one business
    and the primary key alone is guessable, so any mismatch is indistinguishable
    from a missing run.
    """
    try:
        run_id = int(run_id)
    except (TypeError, ValueError):
        abort(404)

    run = db.session.get(ImportRun, run_id)
    if run is None or run.business_id != business_id or run.status != STAGED_STATUS:
        abort(404)
    return run


def staged_records(run):
    """Decode the rows staged against a run."""
    if not run.staged_rows:
        return []
    try:
        records = json.loads(run.staged_rows)
    except (TypeError, ValueError):
        return []
    return records if isinstance(records, list) else []


def complete_import(run, result=None, status=COMMITTED_STATUS, error=None):
    """Close a staged run, record its outcome, and purge the staged rows."""
    result = result or {}
    run.status = status
    run.imported_count = int(result.get('imported') or 0)
    run.duplicate_count = int(result.get('duplicates') or 0)
    run.errors = json.dumps(result.get('errors') or [], default=str)
    run.error_count = len(result.get('errors') or [])
    run.completed_at = datetime.now(timezone.utc)
    run.staged_rows = None
    if error is not None and not run.error_count:
        run.errors = json.dumps([str(error)], default=str)
        run.error_count = 1
    return run


def purge_stale_staged_runs(older_than_hours=24):
    """Delete abandoned ``staged`` runs older than the cutoff.

    Committed and failed runs are never touched, so the outcome of a completed
    import is never removed by housekeeping.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
    stale = ImportRun.query.filter(
        ImportRun.status == STAGED_STATUS,
        ImportRun.created_at < cutoff,
    ).all()
    for run in stale:
        db.session.delete(run)
    return len(stale)


def commit_import(business_id, user_id, run, action, result):
    """Stage the successful outcome of a run alongside its audit entry.

    Both writes stay in the caller's transaction so the run row, the audit
    entry, and the imported data commit or roll back together (ADR-0009).
    """
    complete_import(run, result, COMMITTED_STATUS)
    record_user_action(
        business_id,
        user_id,
        action,
        'import_runs',
        run.id,
        {
            'filename': run.filename,
            'row_count': run.row_count,
            'imported': run.imported_count,
            'duplicates': run.duplicate_count,
            'error_count': run.error_count,
        },
    )
    return run


def fail_import(business_id, user_id, run_id, action, error):
    """Close a run as failed and audit the attempt after a rollback.

    Called once the caller's transaction has been rolled back, so the run row is
    reloaded rather than reusing the expired instance.
    """
    run = db.session.get(ImportRun, run_id)
    if run is None:
        return None
    complete_import(run, status=FAILED_STATUS, error=error)
    record_user_action(
        business_id,
        user_id,
        action,
        'import_runs',
        run.id,
        {'filename': run.filename, 'error': str(error)},
    )
    return run


def flash_import_result(label, result, run=None):
    """Flash an import summary, with a link to the full rejected-row list."""
    message = (
        f'Imported {result["imported"]} {label.lower()} row(s); '
        f'{result["duplicates"]} duplicate(s) skipped.'
    )
    errors = result.get('errors') or []
    if errors:
        message += f' {len(errors)} row(s) had errors.'
    flash(message, 'success' if result['imported'] else 'warning')
    for error in errors[:MAX_FLASHED_ERRORS]:
        flash(error, 'warning')
    if errors and run is not None:
        flash(
            'Download all rejected rows: '
            f'<a href="{url_for("imports.import_error_download", run_id=run.id)}">'
            'rejected-rows.xlsx</a>',
            'warning',
        )