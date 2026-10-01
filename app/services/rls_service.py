"""Postgres row-level security for multi-tenant tables.

Every multi-tenant table carries a ``business_id``. When a request is served on
behalf of an authenticated user, the SQLAlchemy ``after_begin`` event applies
``SELECT set_config('app.business_id', ..., true)`` to each new transaction so
that a Postgres policy constrains every read and write in that transaction to
that business — even for hand-written SQL that forgets its ``WHERE`` clause.

Requests without an authenticated business context (login, webhooks, CLI,
background jobs, the superadmin console) leave the GUC unset, and the policy
deliberately allows those through: RLS here is defense-in-depth against
application-level tenant leaks, not a substitute for authentication.

SQLite (the development database) has no policies; the helpers are dialect-
guarded no-ops there, and the app-layer ``business_id`` filters keep working.
"""

import logging

from sqlalchemy import event, inspect, text

logger = logging.getLogger(__name__)

RLS_BYPASS_TABLES = {"alembic_version"}
# Nullable business_id rows (e.g. anonymous audit events) must stay writable
# while a tenant context is set, so audit tables get a NULL-tolerant policy.
NULLABLE_BUSINESS_ID_TABLES = {"audit_logs"}


def _engine(app):
    return app.extensions["sqlalchemy"].engine


def is_postgres(engine):
    return engine.dialect.name == "postgresql"


def _tenant_tables(metadata):
    tables = []
    for name, table in sorted(metadata.tables.items()):
        if name in RLS_BYPASS_TABLES:
            continue
        if "business_id" in table.columns:
            tables.append((name, "business_id"))
        elif name == "businesses":
            tables.append((name, "id"))
    return tables


def _policy_predicates(table_name, column):
    if table_name in NULLABLE_BUSINESS_ID_TABLES:
        tenant_clause = (
            f"({column} IS NULL OR {column} = current_setting('app.business_id')::integer)"
        )
    else:
        tenant_clause = f"{column} = current_setting('app.business_id')::integer"
    unset_clause = "current_setting('app.business_id', true) IS NULL"
    using = f"{unset_clause} OR {tenant_clause}"
    check = f"{unset_clause} OR {tenant_clause}"
    return using, check


def ensure_rls_policies(app=None):
    """Enable FORCE RLS with per-tenant policies on every multi-tenant table.

    Idempotent: policies are created only when missing, and enabling RLS is
    repeatable. Individual failures are logged and skipped so a host that
    refuses the DDL cannot take the whole application down.
    """
    from app.models import db

    engine = db.engine
    if not is_postgres(engine):
        return []

    tables = _tenant_tables(db.metadata)
    enabled = []
    for table_name, column in tables:
        try:
            # One transaction per table so a single failure cannot poison the rest.
            with engine.begin() as connection:
                using, check = _policy_predicates(table_name, column)
                connection.execute(text(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY'))
                connection.execute(text(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY'))
                policy_name = f"rls_{table_name}_tenant"
                connection.execute(text(
                    f"""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_policies
                            WHERE schemaname = current_schema()
                              AND tablename = '{table_name}'
                              AND policyname = '{policy_name}'
                        ) THEN
                            EXECUTE $policy$
                                CREATE POLICY {policy_name} ON "{table_name}"
                                FOR ALL
                                TO PUBLIC
                                USING ({using})
                                WITH CHECK ({check})
                            $policy$;
                        END IF;
                    END $$;
                    """
                ))
                enabled.append(table_name)
        except Exception as exc:  # noqa: BLE001 - policy DDL must not kill boot
            logger.warning("RLS policy for %s not applied: %s", table_name, exc)
    return enabled


def install_rls_context():
    """Apply the tenant GUC to every new transaction on the routed session."""
    from app.models import db

    def _apply_tenant_context(session, transaction, connection):
        if not is_postgres(connection.engine):
            return
        business_id = session.info.get("rls_business_id")
        if business_id is None:
            return
        connection.execute(
            text("SELECT set_config('app.business_id', :business_id, true)"),
            {"business_id": str(business_id)},
        )

    session_class = db.session.session_factory.class_
    if not event.contains(session_class, "after_begin", _apply_tenant_context):
        event.listen(session_class, "after_begin", _apply_tenant_context)


def set_rls_context(session, business_id):
    """Record the tenant GUC to apply at the start of every transaction."""
    session.info["rls_business_id"] = business_id
