"""RLS policy helpers (dialect-gated).

The Postgres policy/isolation assertions run against a real PostgreSQL backend
when ``RLS_TEST_DATABASE_URL`` (or ``DATABASE_URL``) points at one; on SQLite —
the development database — the helpers are no-ops and that is what is asserted
here.
"""

import pytest


def test_rls_helpers_are_noop_on_sqlite(app):
    from app.services.rls_service import ensure_rls_policies, is_postgres
    from models import db

    assert not is_postgres(db.engine)
    assert ensure_rls_policies() == []


@pytest.fixture
def pg_engine():
    import os

    from sqlalchemy import create_engine

    url = os.environ.get("RLS_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url or not url.startswith("postgres"):
        pytest.skip("RLS policy tests require a PostgreSQL DATABASE_URL")

    from app import create_app
    from config import DevelopmentConfig

    app = create_app(DevelopmentConfig)  # also bootstraps RLS policies
    yield app
    from models import db

    db.session.remove()


def test_rls_policies_applied_to_tenant_tables(pg_engine):
    from sqlalchemy import text

    from models import db

    with db.engine.connect() as connection:
        policies = connection.execute(text(
            "SELECT tablename, COUNT(*) AS policies FROM pg_policies "
            "GROUP BY tablename ORDER BY tablename"
        )).all()
        forced = connection.execute(text(
            "SELECT COUNT(*) FROM pg_tables "
            "WHERE rowsecurity AND forcerowsecurity AND schemaname = 'public'"
        )).scalar_one()
    protected = {row[0] for row in policies}
    assert protected, "no RLS policies found on tenant tables"
    assert "products" in protected
    assert "users" in protected
    assert forced >= len(protected)


def test_tenant_isolation_via_direct_sql(pg_engine):
    from sqlalchemy import text

    from models import db

    with db.engine.connect() as connection:
        businesses = connection.execute(
            text("SELECT id FROM businesses ORDER BY id LIMIT 2")
        ).all()
        if len(businesses) < 2:
            pytest.skip("needs two businesses to prove isolation")
        tenant_a, tenant_b = businesses[0][0], businesses[1][0]

        connection.execute(
            text("SELECT set_config('app.business_id', :biz, true)"),
            {"biz": str(tenant_a)},
        )
        visible = connection.execute(text(
            "SELECT DISTINCT business_id FROM products"
        )).all()
        assert {row[0] for row in visible} <= {tenant_a}, (
            "RLS did not constrain direct SQL to tenant A"
        )

        connection.execute(
            text("SELECT set_config('app.business_id', :biz, true)"),
            {"biz": str(tenant_b)},
        )
        visible = connection.execute(text(
            "SELECT DISTINCT business_id FROM products"
        )).all()
        assert {row[0] for row in visible} <= {tenant_b}
