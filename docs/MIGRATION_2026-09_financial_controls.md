# Financial Controls Migration Guide

This release adds transaction auditing, journal reversal metadata, a business close-through date, and revenue-recognition schedules. It does not add multi-currency support.

## Before deployment

1. Take a verified database backup and test restoring it.
2. Deploy to a staging database first. The migration has not been verified against your production database as part of this change.
3. Check the current Alembic revision with `flask db current`; this migration expects `20260817_merge_heads`.
4. Review the new close-period, reversal, and revenue-recognition procedures with the accounting owner.

## Apply the migration

Run from the application environment after deploying the code:

```bash
flask db upgrade
flask db current
```

The migration:

- Adds nullable `businesses.last_closed_period_date`; no existing period is automatically closed.
- Adds reversal pointer and reason columns to `journal_entries`; existing entries remain unchanged.
- Creates `revenue_recognition_schedules`; no existing invoices are automatically deferred.

No data backfill is required. The new schedule is business-scoped and references an invoice and two chart-of-account entries.

## Post-migration checks

1. Confirm `flask db current` reports the latest deployed migration revision.
2. Run the accounting and reporting test suites.
3. In staging, verify a journal reversal creates a balanced opposite entry and preserves the original.
4. Verify aging reports subtract linked receipts and approved payments as of the selected date.
5. Verify users with the admin/accountant role can close a period, and that a write dated on or before the close-through date is rejected.
6. Verify only admins see and can submit the period reopen action; check that reopening clears the close date and records the change in the audit log.
7. Verify a posted invoice can be deferred and recognized through a date without duplicate recognition on retry.
8. Confirm the audit log excludes password hashes and bank account numbers.

## Rollback

The downgrade removes the revenue-recognition schedule table and drops the period-close and reversal columns. Any schedule state, close-through date, and reversal metadata written after upgrade will be lost. Do not downgrade a production database after using these features unless the business has approved that data loss and a verified backup is available. Downgrade only with the application stopped and a reviewed recovery plan:

```bash
flask db downgrade 20260817_merge_heads
```

## Period reopen procedure

An administrator may reopen the currently closed period from **Accounting → Journal Entries → Period Close**. The action requires explicit confirmation, clears the close-through date (unlocking all dates), and is recorded in the business audit log. Accountants may close and advance the close date but cannot reopen it. Reclose the period after corrections and review are complete.

## Accounting limitations

- Revenue recognition is straight-line and time-based only; it does not automate IFRS 15/ASC 606 contract or performance-obligation analysis.
- Tax presentation remains a simple informational estimate, not a statutory or jurisdiction-specific tax computation.
- Multi-currency accounting remains outside this release.

## Separate demo database

Demo signup and request routing are described in [the separate Neon demo database guide](./MIGRATION_2026-09_demo_workspace_database.md).
