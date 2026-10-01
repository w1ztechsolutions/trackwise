"""Transactional audit logging for financially significant ORM changes."""

import json

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.scoping import scoped_session
from app.models.accounting import Business


AUDITED_TABLES = {
    "businesses",
    "branches",
    "cost_centers",
    "demo_workspaces",
    "chart_of_accounts",
    "products",
    "warehouses",
    "customers",
    "suppliers",
    "purchases",
    "purchase_items",
    "sales",
    "sale_items",
    "expenses",
    "stock_transactions",
    "stock_movements",
    "invoices",
    "invoice_items",
    "receipts",
    "bills",
    "bill_items",
    "payments",
    "bank_statements",
    "journal_entries",
    "journal_lines",
    "production_batches",
    "material_usages",
    "finished_good_outputs",
    "approval_requests",
    "approval_actions",
    "approval_configs",
    "users",
    "subscriptions",
    "revenue_recognition_schedules",
    "settings",
    "financial_categories",
    "line_items",
    "staff",
    "expense_budgets",
    "budgets",
    "budget_line_items",
    "purchase_returns",
}

SENSITIVE_FIELDS = {
    "password_hash",
    "bank_account_number",
    "stripe_subscription_id",
}

PERIOD_DATE_FIELDS = {
    "journal_entries": "entry_date",
    "sales": "sale_date",
    "purchases": "purchase_date",
    "expenses": "expense_date",
    "invoices": "invoice_date",
    "receipts": "receipt_date",
    "bills": "bill_date",
    "payments": "payment_date",
    "stock_transactions": "timestamp",
    "stock_movements": "timestamp",
    "production_batches": "production_date",
    "purchase_returns": "return_date",
}


class AuditLogImmutableError(Exception):
    """Raised when application code attempts to alter an existing audit log."""


class AuditedBulkMutationError(Exception):
    """Raised when bulk ORM DML would bypass per-record audit events."""


def _guard_closed_periods(session, _flush_context, _instances):
    candidates = []
    business_ids = set()
    for instance in session.new.union(session.dirty).union(session.deleted):
        field = PERIOD_DATE_FIELDS.get(getattr(instance, "__tablename__", ""))
        if not field:
            continue
        if instance in session.dirty:
            state = inspect(instance)
            changed = {
                attribute.key
                for attribute in state.mapper.column_attrs
                if state.attrs[attribute.key].history.has_changes()
            }
            if not changed:
                continue
            if (
                instance.__tablename__ == "journal_entries"
                and changed <= {"reversed_by_entry_id", "reversal_reason"}
            ):
                continue
            if (
                instance.__tablename__ == "invoices"
                and changed == {"status"}
                and instance.status in {"paid", "partially_paid"}
            ):
                continue
        business_id = getattr(instance, "business_id", None)
        transaction_date = getattr(instance, field, None)
        if business_id is not None and transaction_date is not None:
            business_ids.add(business_id)
            candidates.append((business_id, transaction_date))

    if not candidates:
        return

    connection = session.connection()
    closed_dates = dict(connection.execute(
        select(Business.id, Business.last_closed_period_date).where(
            Business.id.in_(business_ids)
        ).with_for_update()
    ).all())

    from app.services.period_service import PeriodClosedError, as_date

    for business_id, transaction_date in candidates:
        closed_through = closed_dates.get(business_id)
        if closed_through and as_date(transaction_date) <= closed_through:
            raise PeriodClosedError(
                f"Accounting period is closed through {closed_through.isoformat()}; "
                "transactions in that period cannot be changed."
            )


def _before_flush(session, flush_context, instances):
    if any(
        getattr(instance, "__tablename__", None) == "audit_logs"
        for instance in session.dirty.union(session.deleted)
    ):
        raise AuditLogImmutableError("Audit log records cannot be changed or deleted")
    _guard_closed_periods(session, flush_context, instances)

    from app.models.accounting import AuditLog

    connection = session.connection()
    actor_snapshots = {}
    related_business_ids = {}
    for instance in session.new.union(session.dirty).union(session.deleted):
        if getattr(instance, "__tablename__", None) not in AUDITED_TABLES:
            continue
        if _business_id(instance) is None:
            business_id = _related_business_id(instance, connection)
            if business_id is not None:
                related_business_ids[id(instance)] = business_id
        actor_id = _actor_id(session, instance)
        if actor_id is not None and actor_id not in actor_snapshots:
            actor_snapshots[actor_id] = _lookup_actor(session, actor_id, connection)
    session.info["audit_actor_snapshots"] = actor_snapshots
    session.info["audit_related_business_ids"] = related_business_ids

    for instance in session.new:
        if _carries_actor_snapshot(instance) and instance.user_id is not None:
            instance.actor_name, instance.actor_email = _lookup_actor(
                session,
                instance.user_id,
                connection,
            )


def _carries_actor_snapshot(instance):
    """True for rows that keep their own actor name/email snapshot (ADR-0009).

    Only ``audit_logs`` and ``import_runs`` store ``actor_name``/``actor_email``,
    so this never reaches the snapshot columns of ordinary financial records.
    """
    return all(
        hasattr(instance, attribute)
        for attribute in ("user_id", "actor_name", "actor_email")
    )


def _lookup_actor(session, actor_id, connection):
    from app.models import User

    row = connection.execute(
        select(User.name, User.email).where(User.id == actor_id)
    ).one_or_none()
    actor = next(
        (
            instance
            for instance in session.identity_map.values()
            if isinstance(instance, User) and instance.id == actor_id
        ),
        None,
    )
    if actor is not None:
        state = inspect(actor)
        values = {}
        for field in ("name", "email"):
            history = state.attrs[field].history
            values[field] = (
                history.deleted[0]
                if history.has_changes() and history.deleted
                else getattr(row, field)
                if history.has_changes() and row
                else getattr(actor, field)
            )
        return values["name"], values["email"]

    return (row.name, row.email) if row else (None, None)


def _snapshot(instance, fields=None):
    mapper = inspect(instance).mapper
    names = fields or (column.key for column in mapper.column_attrs)
    return {
        name: getattr(instance, name)
        for name in names
        if name not in SENSITIVE_FIELDS and hasattr(instance, name)
    }


def _business_id(instance):
    value = getattr(instance, "business_id", None)
    if value is None and instance.__tablename__ == "businesses":
        value = getattr(instance, "id", None)
    return value


def _related_business_id(instance, connection):
    if instance.__tablename__ == "journal_lines":
        from app.models.accounting import JournalEntry

        return connection.execute(
            select(JournalEntry.business_id).where(
                JournalEntry.id == instance.journal_entry_id
            )
        ).scalar_one_or_none()
    if instance.__tablename__ == "approval_actions":
        from app.models.approval import ApprovalRequest

        return connection.execute(
            select(ApprovalRequest.business_id).where(
                ApprovalRequest.id == instance.approval_request_id
            )
        ).scalar_one_or_none()
    return None


def _actor_id(session, instance):
    for key in ("audit_actor_id", "actor_id", "created_by", "user_id"):
        actor_id = session.info.get(key) if key == "audit_actor_id" else getattr(instance, key, None)
        if actor_id is not None:
            return actor_id
    return None


def _actor_snapshot(session, actor_id, connection):
    if actor_id is None:
        return None, None
    snapshots = session.info.get("audit_actor_snapshots", {})
    if actor_id in snapshots:
        return snapshots[actor_id]
    return _lookup_actor(session, actor_id, connection)


def _audit_after_flush(session, _flush_context):
    from app.models.accounting import AuditLog

    connection = session.connection()
    changes = []

    for instance in session.new:
        if instance.__tablename__ in AUDITED_TABLES:
            changes.append((instance, "CREATE", None, _snapshot(instance)))

    for instance in session.dirty:
        if instance.__tablename__ not in AUDITED_TABLES:
            continue
        state = inspect(instance)
        changed = {
            attribute.key: state.attrs[attribute.key].history
            for attribute in state.mapper.column_attrs
            if state.attrs[attribute.key].history.has_changes()
            and attribute.key not in SENSITIVE_FIELDS
        }
        if changed:
            old_values = {
                name: history.deleted[0] if history.deleted else None
                for name, history in changed.items()
            }
            new_values = {
                name: history.added[0] if history.added else getattr(instance, name)
                for name, history in changed.items()
            }
            changes.append((instance, "UPDATE", old_values, new_values))

    for instance in session.deleted:
        if instance.__tablename__ in AUDITED_TABLES:
            changes.append((instance, "DELETE", _snapshot(instance), None))

    for instance, action, old_values, new_values in changes:
        business_id = _business_id(instance)
        if business_id is None:
            business_id = session.info.get("audit_related_business_ids", {}).get(
                id(instance)
            )
        if business_id is None:
            business_id = _related_business_id(instance, connection)
        actor_id = _actor_id(session, instance)
        actor_name, actor_email = _actor_snapshot(session, actor_id, connection)
        connection.execute(
            AuditLog.__table__.insert().values(
                business_id=business_id,
                user_id=actor_id,
                actor_name=actor_name,
                actor_email=actor_email,
                action=action,
                table_name=instance.__tablename__,
                record_id=getattr(instance, "id", None),
                old_values=(
                    json.dumps(old_values, default=str, sort_keys=True)
                    if old_values is not None else None
                ),
                new_values=(
                    json.dumps(new_values, default=str, sort_keys=True)
                    if new_values is not None else None
                ),
            )
        )
    session.info.pop("audit_actor_snapshots", None)
    session.info.pop("audit_related_business_ids", None)


def _guard_audit_bulk_mutation(execute_state):
    statement_table = getattr(execute_state.statement, "table", None)
    if not (execute_state.is_update or execute_state.is_delete) or statement_table is None:
        return
    if statement_table.name == "audit_logs":
        raise AuditLogImmutableError("Audit log records cannot be changed or deleted")
    if statement_table.name in AUDITED_TABLES:
        raise AuditedBulkMutationError(
            "Bulk changes to audited records are disabled; load and mutate ORM records individually."
        )


def _session_class(target):
    """Resolve an event target to the Session subclass the listeners belong on.

    A ``scoped_session`` is resolved to the class it constructs. Listeners are
    never left on the global ``sqlalchemy.orm.Session``, so they do not apply to
    sessions the application never created.
    """
    if target is None:
        return Session
    if isinstance(target, scoped_session):
        return target.session_factory.class_
    return target


def install_audit_listeners(target=None):
    """Register the audit listeners on ``target``'s session class.

    ``target`` is normally the scoped session owned by the application's
    ``db`` handle; its session class is used so the listeners are scoped to
    sessions this application creates. Passing nothing falls back to the global
    ``sqlalchemy.orm.Session``, which is only appropriate for standalone
    processes that deliberately want process-wide auditing.
    """
    session_class = _session_class(target)
    if not event.contains(session_class, "after_flush", _audit_after_flush):
        event.listen(session_class, "after_flush", _audit_after_flush)
    if not event.contains(session_class, "before_flush", _before_flush):
        event.listen(session_class, "before_flush", _before_flush)
    if not event.contains(session_class, "do_orm_execute", _guard_audit_bulk_mutation):
        event.listen(
            session_class,
            "do_orm_execute",
            _guard_audit_bulk_mutation,
        )


def record_user_action(business_id, user_id, action, table_name, record_id=None, details=None):
    """Stage a non-model user action in the current database transaction."""
    from app.models.accounting import AuditLog

    from app.models import db

    db.session.add(AuditLog(
        business_id=business_id,
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        new_values=json.dumps(details, default=str, sort_keys=True) if details else None,
    ))
