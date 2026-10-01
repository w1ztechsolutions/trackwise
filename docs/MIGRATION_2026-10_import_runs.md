# Migration Guide: Excel Import Data Loss and Audit Logging Fixes

**Applies to:** TrackWise releases containing `20261001_import_runs`
**Date:** 2026-10-01

## What changed

Spreadsheet imports were reworked in three areas:

1. **Import rows are staged server-side.** The import wizard used to post the entire
   parsed workbook back to the application as a client-supplied JSON `payload`. It now
   carries an `import_run_id` and the application reads the staged rows from the new
   `import_runs` table.
2. **Every import attempt is audited.** Successful and failed imports both write an
   entry to `audit_logs`. Budget variance import no longer relies on the report-access
   decorator, which had recorded imports that never happened.
3. **The import wizard gained column auto-detect and a date-order selector.** Repeated
   worksheet headers are disambiguated instead of overwriting each other.

`import_runs` is an operational log, not a financial record. It is deliberately excluded
from the audited-table set; its auditability comes from the explicit `IMPORT_*` and
`IMPORT_*_FAILED` entries in `audit_logs`. See
[ADR-0013](adr/ADR-0013-import-run-records-and-server-side-row-staging.md).

## Schema change

One new table, no data migration and no backfill:

| Migration | Effect |
| --- | --- |
| `20261001_import_runs` | Creates `import_runs` with indexes on `business_id` and (`business_id`, `status`) |

`downgrade()` drops the table. Existing migrations are unchanged.

## Upgrade steps

1. **Back up the database** using the procedure in [Backup and Retention](BACKUP_AND_RETENTION.md).

2. **Apply the migration** in the ordinary way:

   ```bash
   flask db upgrade
   ```

   Confirm a single head before and after:

   ```bash
   flask db heads
   ```

   The expected head is `20261001_import_runs`.

3. **For a demo database**, use the demo-only app factory instead:

   ```bash
   flask --app 'app:create_demo_migration_app' db upgrade
   ```

4. **Restart the application.** Audit listeners are installed during application
   creation; no separate step is required.

5. **Verify** that the wizard still imports:

   - Upload a small bank statement workbook and complete the mapping step.
   - Confirm the result message and, on a partially failing file, that the
     "Download all rejected rows" link returns an XLSX.

## No data backfill is required

There is no historical data to migrate. Imports completed before this release have no
`import_runs` row, and their audit trail is unchanged. The `IMPORT_*` audit actions only
exist for imports attempted after the upgrade.

## Behaviour changes to be aware of

- **In-flight wizard sessions are refused, not failed.** A mapping submission submitted
  from a browser tab opened before the upgrade carries the old `payload` field. The
  application detects it, shows "This import session has expired. Upload the workbook
  again and map the columns.", and creates no records. Users re-upload the file; there
  is no data loss because the previous step's rows were never committed.
- **Report views that return 4xx or 5xx are no longer audited.** A report view that
  aborts no longer leaves a `REPORT_VIEW` entry suggesting it was served.
- **Budget variance import writes `BUDGET_IMPORT_FAILED` instead of `BUDGET_IMPORT`**
  when it fails. Consumers of the audit log should expect both actions.
- **Abandoned staged runs are purged.** A `staged` run older than 24 hours is deleted on
  the next workbook upload. `committed` and `failed` runs are never deleted.
- **Uploaded rows are not retained.** `staged_rows` is set to `NULL` when a run completes,
  so only counts, the column mapping, and the rejection messages persist.

## Rollback

1. Revert the application code to the previous release.
2. Leave the `import_runs` table in place. It is additive and unused by the previous
   code, so no downgrade is required for a code-only rollback.
3. Only run `flask db downgrade` if the `import_runs` table itself must be removed. Doing
   so discards the recorded outcome of every import made since the upgrade.

Rollback loses the staged import audit trail for the period the new code was running, so
prefer a forward fix.

## Post-upgrade checks

| Check | Expected |
| --- | --- |
| `flask db heads` | Single head: `20261001_import_runs` |
| `GET /imports/<run_id>/errors` for the business's own run | `200` with an XLSX body |
| `GET /imports/<run_id>/errors` for another business's run | `404` |
| Successful import | `audit_logs` row `IMPORT_<ENTITY>` with filename and counts |
| Failed import | `audit_logs` row `IMPORT_<ENTITY>_FAILED`, and no `IMPORT_<ENTITY>` |
| Failed budget import | `BUDGET_IMPORT_FAILED`, and no `BUDGET_IMPORT` |
| Completed run | `staged_rows IS NULL`, `status` in (`committed`, `failed`) |