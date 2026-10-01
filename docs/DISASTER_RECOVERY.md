# Production Disaster Recovery Procedure

Use this procedure when production data or the TrackWise service is unavailable, corrupted, or suspected to be compromised. It assumes production uses PostgreSQL and that usable provider recovery points and/or logical dumps are available. Follow the provider's current instructions for its snapshot/PITR controls; do not assume the provider, Vercel, or this application has already performed a restore.

## Recovery objectives and authority

The service owner must approve and record business-specific recovery objectives. Until approved, use these planning targets for incident preparation only, not as a service guarantee:

- **Target RPO:** no more than 24 hours of data loss, subject to actual backup/PITR coverage.
- **Target RTO:** restore critical service within 8 business hours after a recovery decision.

The incident lead coordinates technical recovery. A database operator performs the restore. The business owner/accounting lead decides whether the recovered accounting state is acceptable. Only the incident lead or delegated service owner authorizes production cutover. Keep a timestamped incident log and record decisions and approvals.

## 1. Stabilize and assess

1. Declare an incident, identify the incident lead and database operator, and start an access-controlled incident log.
2. Determine whether the problem is app/deployment, database availability, accidental change, corruption, or suspected compromise. Check the deployment/provider status and the TrackWise `/health` endpoint without exposing secrets.
3. If unauthorized access or active corruption is possible, restrict writes/access using the hosting/database provider controls. Preserve relevant logs and the affected database state for investigation; do not erase or overwrite evidence.
4. Record the last known-good time, affected deployment/release, observed symptoms, estimated data loss, and candidate backup/PITR points. Notify the business owner and affected operators.
5. Confirm the provider supports the selected recovery point and destination. Choose the latest verified point before the incident, subject to business approval of the resulting RPO/data loss.

## 2. Restore to an isolated target

1. Create a new, private PostgreSQL database or provider branch for recovery. Do not restore over the damaged production database as the first action.
2. Prefer provider point-in-time restore for rapid recovery when its coverage and target time are verified. Otherwise restore a verified custom-format dump into an empty target:

   ```bash
   pg_restore --no-owner --dbname="$RESTORE_DATABASE_URL" trackwise.dump
   ```

   `RESTORE_DATABASE_URL` must refer only to the isolated target. Do not use a production connection string for this test/restore step. A Windows PowerShell equivalent is `pg_restore --no-owner --dbname="$env:RESTORE_DATABASE_URL" trackwise.dump`.
3. Keep the original database and restore point unchanged. Preserve the dump and recovery logs according to the incident/evidence policy.
4. Set up an isolated application environment using the recovered target URL and secrets from the approved secret manager. Do not print or commit connection strings or secret values.
5. Match the application release to the restored schema. Inspect the migration state first. Do not run migrations, seed scripts, or schema bootstrap commands against the source backup or production until the release/schema combination is understood and approved.

## 3. Validate before cutover

On the isolated target, and with an authorized reviewer:

1. Run `python check_db_schema.py` and `python verify_db.py` from the release being considered. Confirm expected tables and migration revision; investigate any failures.
2. Start the application against the isolated database and confirm `/health` succeeds. Exercise sign-in and representative workflows without sending real customer notifications or external payment actions.
3. Verify representative business, user, transaction, audit, and period-close records around the recovery point. Check business/tenant isolation and confirm that no unrelated tenant's access has changed.
4. Run the accounting integrity verification for affected businesses. Reconcile record counts and financial reports with the last approved close evidence and independent records; identify transactions after the recovery point that must be re-entered.
5. Have the accounting/business owner approve the recovered state, known gaps, and estimated data loss. Reject the target and select another recovery point if integrity or completeness is not acceptable.

## 4. Cut over and recover service

1. Announce the planned cutover and put the application into a write-restricted or maintenance state using the hosting controls available to the operator.
2. Take a final protected snapshot of the affected database before changing routing, if it is safe and available.
3. Update the production `DATABASE_URL` in the hosting secret store to the validated recovered database. Keep `DEMO_DATABASE_URL` separate and verify it still points only to the demo database. Do not publish secrets in deployment output.
4. Deploy or restart the approved application release. Verify `/health`, sign-in, tenant boundaries, common workflows, database connectivity, and accounting integrity on the production URL.
5. Re-enable writes only after the incident lead and business owner approve. Tell operators the recovery point, any data that must be re-entered, and any temporary restrictions.
6. Monitor application/provider logs and database health closely. Preserve both the old and recovered database until reconciliation, incident review, and retention requirements permit cleanup.

## 5. Reconcile and close the incident

- Re-enter missing business transactions through supported application workflows with source documents and approvals. Avoid manual SQL repair except under a separately approved, reviewed, and evidenced recovery plan.
- Reconcile recovered and re-entered records, bank/cash activity, journals, and period-close status. If a period was reopened or its boundary changed, use the [period-close runbook](PERIOD_CLOSE_RUNBOOK.md) to reassess and close it again.
- Record the root cause, selected recovery point, estimated/actual RPO and RTO, validation evidence, approvals, data loss, and follow-up actions.
- Rotate credentials if compromise is suspected, including database and hosting access, `SECRET_KEY` as appropriate for the incident, and relevant integration secrets. Assess session invalidation and external service access.
- Restore normal backup monitoring and retention; schedule a restore test if the incident exposed a gap.

## Prohibited recovery shortcuts

- Do not run `seed.py`, `db.drop_all()`, destructive SQL, or migration/bootstrap commands as a recovery shortcut.
- Do not restore a multi-tenant full database dump over production to recover one business.
- Do not point the demo application at production data or the recovery target.
- Do not declare recovery successful based solely on the app starting or `/health` returning 200.

See [Backup and Retention](BACKUP_AND_RETENTION.md) for backup creation, protection, and restore-test requirements.
