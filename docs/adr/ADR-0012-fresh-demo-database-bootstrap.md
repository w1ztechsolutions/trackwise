# ADR-0012: Fresh Demo Database Bootstrap

**Feature:** Initialize a new isolated demo database from current SQLAlchemy ORM metadata and mark the current Alembic heads as applied.

**Why chosen:**

- The historical migration chain is not compatible with a fresh PostgreSQL database: it assumes a non-portable settings constraint name and alters a `material_usages` table that no migration creates.
- Existing migration files must remain immutable because they may already have been applied in production.
- The demo database is a disposable, isolated environment and can be safely initialized from current model metadata when it is empty.
- A dedicated app factory makes the demo database the primary connection for the CLI and keeps production schema-repair startup checks out of the bootstrap path.

**Strengths:**

- Prevents demo schema initialization from connecting to or repairing production.
- Refuses to bootstrap if application rows or unmapped tables are present.
- Creates all currently mapped tables and verifies the Alembic head(s) after stamping.
- Keeps future schema changes on the standard forward-migration path.

**Alternatives considered:**

- Edit the historical migration files — rejected because those revisions may already have been applied in production.
- Stamp an empty database at head without creating its schema — rejected because it would leave the application tables absent.
- Run the legacy migration chain against the new demo database — rejected because it fails on assumptions not met by a fresh database.

**Operational constraint:**

Use `flask --app 'app:create_demo_migration_app' demo-db-bootstrap` only for an empty demo database. For later schema changes, use `flask --app 'app:create_demo_migration_app' db upgrade`. Production continues to use its ordinary migration procedure.
