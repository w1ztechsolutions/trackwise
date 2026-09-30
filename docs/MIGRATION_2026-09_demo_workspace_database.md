# Separate Neon Demo Database Guide

The demo flow stores all demo businesses, users, and activity in a dedicated database. Ordinary email/password authentication remains connected to `DATABASE_URL`. Do not configure `DEMO_DATABASE_URL` with a production database.

## Neon setup

1. Create a separate Neon project or branch dedicated to demo data. Do not use the production branch or endpoint.
2. Configure the app environment with:
   - `DATABASE_URL`: the existing production connection.
   - `DEMO_DATABASE_URL`: the demo project's connection.
   - `DEMO_MODE_ENABLED=true`.
3. Keep both connection strings private. Startup rejects matching endpoint/database identities, including Neon pooler aliases, but distinct Neon branch endpoints can still point to an unintended branch; verify the project and branch in Neon.
4. Initialize each database using its isolated procedure:

   ```bash
   flask db upgrade
   flask --app 'app:create_demo_migration_app' demo-db-bootstrap
   ```

   The first command upgrades the production schema. The demo command uses an app factory whose primary database is `DEMO_DATABASE_URL`; it never initializes the production database. The demo bootstrap refuses to proceed if it finds unmapped tables or rows in application tables. On an empty database it creates the current ORM schema and stamps the current Alembic head(s).
   
   Do not use `flask db upgrade` against a fresh demo database. The legacy migration chain is not fresh-install compatible: revision `b55c4e6f8a21` expects a settings constraint name that is not portable and alters `material_usages`, which is not created by the migration history. The bootstrap is intentionally limited to an empty demo database; existing demo data must be preserved and upgraded through normal forward migrations.
5. Open `/demo`. A visitor enters a business name and selects a role. New names create a demo business, starter chart of accounts, and a random internal user. If the normalized business name already exists, the visitor can proceed into that shared business (a new internal user is created in the selected role) or choose another name.

For later demo schema updates, run Alembic with the demo-only factory after reviewing the pending migrations:

```bash
flask --app 'app:create_demo_migration_app' db upgrade
```

This targets `DEMO_DATABASE_URL`; it does not run production schema-repair checks.

## Database isolation behavior

- Normal `/login` form submissions explicitly route credential lookups to `DATABASE_URL`.
- Demo signup, confirmation, user creation, and authenticated app requests are routed to `DEMO_DATABASE_URL` by a signed Flask session marker.
- The marker is cleared on logout. If the demo engine is unavailable, demo-bound ORM queries fail closed rather than falling back to production.
- Demo user emails/passwords are random internal values and are not shown to visitors. Role selection creates a distinct user record so visitors can test the selected role. Admins cannot create additional users from demo user management; the `/users/create` page and endpoint are unavailable in demo sessions.
- The demo database is public/shared while demo mode is enabled. Any visitor can create workspaces or join an existing workspace by name; do not use this feature for private accounts or real data.
- Business-name matching trims leading/trailing whitespace, collapses repeated whitespace, and ignores case. It is exact after normalization, not fuzzy similarity matching.

## Disabling and data cleanup

Set `DEMO_MODE_ENABLED=false` or remove it to hide and disable demo entry. This does not delete data. Retain or delete demo data using the demo database's normal backup and retention process; never run cleanup against `DATABASE_URL` when intending to clear demo content.
