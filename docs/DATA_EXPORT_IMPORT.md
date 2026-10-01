# Data Export and Import Procedures

This guide distinguishes report copies, supported CSV input, and full database backups. TrackWise does not currently provide a general-purpose full-business export/import or tenant-selective restore workflow. Confirm an export/import request's scope and authorization before handling financial or personal data.

## Report copies

Use the relevant in-app financial report and its available PDF/print action for a human-readable report copy. Confirm the business, date range, and report filters before export. Store the PDF in the approved access-controlled location, apply the business's retention rules, and do not treat a report PDF as a restorable data backup.

The documented JSON API is not a complete export interface: it provides read access to products, suppliers, and accounting verification, not a portable dump of all business records. Do not promise or imply a complete export from those endpoints.

## Full-database export and restore

For a complete production copy, use the protected PostgreSQL logical-dump procedure in [Backup and Retention](BACKUP_AND_RETENTION.md). A full dump may contain data for multiple businesses and includes sensitive records. Restrict it accordingly.

For a full-database restore, use an isolated, empty PostgreSQL target and the [Disaster Recovery](DISASTER_RECOVERY.md) validation and approval steps. A database restore replaces a database state; it is not a merge and is not a safe way to restore one business from a multi-tenant database. Never import a production dump into a shared development/demo database without explicit authorization, access controls, and an approved sanitization process.

## Supported bank-statement CSV import

The supported paste-based CSV flow imports bank statement lines for one selected bank account. It does not import general ledger journals, invoices, customers, suppliers, or an entire business.

1. Obtain the statement from the bank and protect the original. Confirm it is for the intended business, bank account, and date range.
2. Convert each transaction to one line with these comma-separated fields:

   ```text
   YYYY-MM-DD,amount,description,reference
   2026-09-01,15000.00,Deposit from Customer A,TXN001
   2026-09-02,-5000.00,Payment to Supplier B,CHQ002
   ```

   Use positive amounts for deposits and negative amounts for withdrawals. Do not include a header row. The current parser splits each line on commas rather than interpreting fully quoted CSV fields; therefore do not include commas inside a description or reference. Keep the original bank file as source evidence.
3. In TrackWise, open **Accounting → Bank Reconciliation → Import Statement**, select the correct bank account, paste the lines, and submit.
4. Review the result and imported statement lines. Resolve rejected/invalid lines from the original source, then reconcile imported items to the appropriate ledger entries. Check for duplicate submissions before importing again; do not assume the import is an idempotent replacement.
5. Retain the original statement, import date, operator, account, and outcome in the approved evidence location.

## Unsupported or unsafe operations

- There is no general bulk business-data import, full-business self-service export, or tenant-only database restore described here. Use approved in-app workflows for individual records; request an implementation or a separately designed, reviewed migration for bulk work.
- Do not hand-edit the production database or use raw SQL inserts to bypass validation, audit logging, business scoping, and accounting rules.
- Do not extract a tenant with ad hoc queries unless the query has been reviewed for `business_id` scoping across every related table and the recipient and purpose are approved. A filtered CSV is not a database backup.
- Do not email unencrypted exports or include them in support tickets, source control, or application logs. Redact or minimize data where practical and delete working copies after the approved retention period.
