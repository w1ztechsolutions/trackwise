# Database Backup and Retention Policy

This is the operational baseline for production TrackWise data. It describes required operator practices; it does not claim that TrackWise itself schedules, monitors, or retains backups. The database provider's actual backup/PITR features and limits depend on the selected service plan and must be confirmed by the service owner.

## Scope and ownership

- Production business, user, accounting, inventory, audit, and configuration records in PostgreSQL are in scope. A separate demo database is a separate data set and must be backed up or intentionally allowed to expire under its own policy.
- SQLite is for development/testing; a local `instance/trackwise.db` is not a production backup strategy.
- The service owner ensures provider-managed recovery is enabled where offered, owns logical backup jobs, access controls, retention, restore tests, and incident evidence, and names an alternate operator.
- Keep application code/releases and database recovery separate. A database dump does not contain deployment environment variables, Flask `SECRET_KEY`, Stripe credentials, Redis credentials, or provider access configuration. Store those separately in an access-controlled secret manager and include recovery of them in the service continuity plan.

## Schedule and retention baseline

Use this baseline unless a stricter legal, contractual, or business requirement applies:

| Copy | Frequency | Minimum retention | Purpose |
|---|---|---|---|
| Provider-managed backup / point-in-time recovery | Continuously or at the finest interval offered; confirm actual coverage and expiry with the provider | At least 7 days of recoverable history, if the plan supports it | Fast recovery from accidental writes or recent corruption |
| Encrypted logical PostgreSQL dump | Daily | 35 days | Portable recovery independent of a provider snapshot |
| Month-end logical dump | Once each month, after the month-end close is approved | 12 months | Period-end recovery and audit support |
| Pre-change logical dump | Before production schema migrations or other high-risk data operations | Retain until the change is accepted and the normal backup retention window has elapsed | Rollback/recovery checkpoint |

If the provider plan cannot meet these targets, document the actual coverage, assess the gap with the business owner, and add an alternate protected backup or change the approved recovery objectives. Never represent unverified provider features as active.

Financial/source-record retention is not the same as backup retention. The business data owner must set retention and deletion periods for live records and exported data with its legal/accounting obligations in mind. Apply legal holds before deleting any copy. Do not shorten a backup's retention to satisfy an application-level deletion request without a documented, authorized policy decision.

## Protection and verification

1. Use TLS for database transfers. Encrypt backup files at rest using provider-managed encryption or approved strong encryption before leaving the trusted environment.
2. Store copies outside the production database account/region where practical. Restrict access to named operators, require MFA where available, and keep backup deletion credentials separate from application credentials.
3. Never commit dumps, upload them to public or personal storage, email them, or include them in ordinary application logs. Treat dumps and report exports as sensitive financial and personal data.
4. After each logical dump, check command success, file size, timestamp, and `pg_restore --list` output. Record the destination, database identity (not its credential-bearing URL), operator, and result in the backup log.
5. Test restoration quarterly into an isolated, access-controlled database. Verify schema/migration state, representative record counts and dates, authentication/tenant boundaries, and accounting integrity before marking the test successful. Never test by overwriting production.
6. Review backup-job outcomes and remaining retention capacity at least monthly. Escalate missed backups or failed restore tests as incidents; do not silently reset the backup-success indicator.
7. Apply the retention table to all copies, including local operator downloads and test restores. Delete expired copies securely unless held by law, contract, or incident investigation.

## Portable PostgreSQL backup

Install PostgreSQL client utilities compatible with the server. Load `DATABASE_URL` from the approved secret store or secure operator environment; do not place a literal credential in a command, script, ticket, or chat.

Bash:

```bash
pg_dump --format=custom --no-owner --file=trackwise.dump "$DATABASE_URL"
pg_restore --list trackwise.dump
```

PowerShell:

```powershell
pg_dump --format=custom --no-owner --file=trackwise.dump "$env:DATABASE_URL"
pg_restore --list trackwise.dump
```

Keep the resulting dump in the protected backup location, encrypt it if that location does not provide approved at-rest encryption, and log the verification result. A successful dump command and readable archive are necessary but do not replace a restore test.

## Demo and local databases

`DEMO_DATABASE_URL` must remain separate from `DATABASE_URL`. Decide explicitly whether demo data is disposable; if it is retained, give it a separate owner and the same access/retention protections. Never use demo data as a production backup. For a development SQLite file, stop all application processes that may write to it before copying; do not apply file-copy guidance to a live production database.

For recovery steps and service restoration, see [Disaster Recovery](DISASTER_RECOVERY.md). For a controlled application-level import/export, see [Data Export and Import](DATA_EXPORT_IMPORT.md).
