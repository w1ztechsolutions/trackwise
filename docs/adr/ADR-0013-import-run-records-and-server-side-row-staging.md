# ADR-0013: Import Run Records and Server-Side Row Staging

**Feature:** Record every spreadsheet import attempt in a first-class `import_runs` table, and hold the uploaded rows server-side between the upload and mapping steps instead of round-tripping them through the browser.

**Why chosen:**

- `audit_logs.details` alone was insufficient. It holds one JSON blob per user action, has no import lifecycle, and no way to recover the rows an import rejected. A partial import of a 5,000-row workbook flashed the first five errors and discarded the rest on redirect.
- An import attempt is an operational fact that needs its own record: what file, which entity, which column mapping, how many rows, how many imported, how many duplicates, how many errors, and which rows failed.
- The wizard previously posted the entire parsed workbook back to the server as a client-supplied JSON `payload`. That made the import data tamperable, tied the request size to the file size, and left nothing on the server between the two steps.
- Staged rows are purged when the run commits, so row contents are not retained; only counts, the column mapping, and the error list persist. Retention therefore holds no customer or financial row data after completion.
- `import_runs` is deliberately **not** added to `AUDITED_TABLES`. It is an operational log, not a financial record. Auditability comes from the explicit `IMPORT_<ENTITY>` / `IMPORT_<ENTITY>_FAILED` entries written to `audit_logs` in the same transaction as the data. Adding the table to the audited set would make the bulk-mutation guard block the legitimate staged-run purge path.
- Date order is a per-import choice defaulting from the device locale. Unambiguous ISO forms are parsed first regardless of the setting, so the default only affects genuinely ambiguous `01/02/2026`-style values.
- This extends [ADR-0009](ADR-0009-financial-audit-and-period-controls.md) to spreadsheet imports. Report-view auditing and period-close enforcement are unchanged by this decision.

**Scope of the extension over ADR-0009:**

| Concern | ADR-0009 | ADR-0013 |
|---|---|---|
| Audit write transaction | Same transaction as the business write | Same transaction as the business write, extended to include the `import_runs` row |
| Actor snapshot | `actor_name` / `actor_email` at event time | Same fields on `import_runs`, identical snapshot semantics |
| Sensitive fields omitted | Secrets and bank account numbers | Unchanged; `import_runs` stores counts, headers, and error messages only |
| Audited tables | Financial and configuration records | Unchanged; `import_runs` excluded, with `audit_logs` carrying the import events |

**Strengths:**

- Rejected rows are recoverable as a downloadable XLSX rather than being discarded after five flashes.
- The import payload is server-held, so a bookmarked or replayed mapping POST cannot inject client-supplied rows.
- Row contents are purged on completion, limiting retained data while keeping the outcome permanently auditable.
- Tenant scope is enforced on every staged-run load, closing the IDOR surface that a guessable integer primary key would otherwise create.

**Alternatives considered:**

- Keep the client-supplied `payload` — rejected because the import data would remain tamperable and unbounded in size.
- Store staged rows in Redis or another external cache — rejected because no cache is wired into `create_app`, and a cache outage would silently drop in-flight imports.
- Keep only `audit_logs` details JSON — rejected because it cannot hold a lifecycle or the rejected-row list.
- Retain staged rows for re-import after a failure — rejected for now; the rejected-row XLSX plus the retained error list covers recovery, and row retention conflicts with the purge decision.
- Add `import_runs` to `AUDITED_TABLES` — rejected because it would block the staged-run purge.