"""Audit Trail report derived from AuditLog records.

Every journal entry creation writes an AuditLog row via
`_log_audit()` in `accounting_service.py`.  This report
surfaces those immutable records so users can see who did what
and when — separate from the General Ledger's per-line attribution.
"""

import json

from app.models import db, AuditLog, User


def get_audit_log(business_id, start_date=None, end_date=None, action=None):
    """Generate an Audit Trail from AuditLog records.

    Args:
        business_id: The business (tenant) to generate the report for
        start_date:  Optional start date filter (datetime)
        end_date:    Optional end date filter (datetime)
        action:      Optional action filter (e.g. 'CREATE')

    Returns:
        dict with `entries` list and filter metadata
    """
    query = (
        db.session.query(AuditLog, User)
        .outerjoin(User, AuditLog.user_id == User.id)
        .filter(AuditLog.business_id == business_id)
    )

    if start_date:
        query = query.filter(AuditLog.timestamp >= start_date)
    if end_date:
        query = query.filter(AuditLog.timestamp <= end_date)
    if action:
        query = query.filter(AuditLog.action == action)

    query = query.order_by(AuditLog.timestamp.desc())

    entries = []
    for log, user in query.all():
        display_name = 'Unknown'
        if user:
            display_name = user.name or user.email or str(user.id)

        entries.append({
            'timestamp': log.timestamp,
            'user_name': display_name,
            'user_email': user.email if user else '',
            'action': log.action,
            'table_name': log.table_name,
            'record_id': log.record_id,
            'old_values': json.loads(log.old_values) if log.old_values else {},
            'new_values': json.loads(log.new_values) if log.new_values else {},
        })

    return {
        'entries': entries,
        'start_date': start_date,
        'end_date': end_date,
        'action': action,
    }
