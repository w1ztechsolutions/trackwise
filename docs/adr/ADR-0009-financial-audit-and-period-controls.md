# ADR-0009: Financial Audit and Period Controls

**Feature:** Record financial source changes transactionally, preserve posted journal history through reversals, and prevent writes to closed periods.

**Why chosen:**

- Financial activity needs an actor-attributed history that commits or rolls back with the business transaction.
- A reversal is a traceable counter-entry; deleting or rewriting a posted entry would obscure the original accounting record.
- A business close-through date gives the application a common cutoff for rejecting back-dated postings and edits.
- Administrators may explicitly reopen a closed period; the close-date change is captured by the transactional audit log. Accountants may close periods but cannot reopen them.
- Audit snapshots must omit authentication secrets and bank account numbers.
- Audit records retain the actor's name and email as they were at event time, independent of later user edits or deactivation.
- Transactional ORM changes, authentication actions, and report views/exports are recorded in the same database transaction as the relevant operation.

**Strengths:**

- Financial record changes and audit events share the database transaction.
- Journal corrections preserve the original entry and identify the reversing entry and reason.
- Period-close enforcement is shared across ORM writes rather than being limited to one UI form.
- Existing audit records cannot be updated or deleted through the application ORM, including bulk ORM DML.
- Audit snapshots cover transaction, inventory, production, approval, account configuration, and user records; report reads and exports are explicit user-action events.

**Alternatives considered:**

- Add audit calls individually to every route — rejected because writes from services, background jobs, or future routes could bypass them.
- Mutate or soft-delete the original entry when correcting it — rejected because this loses clear posted-history semantics.
- Enforce close dates only in the manual journal form — rejected because it misses other financial transaction paths.
- Make period close permanently irreversible — rejected because administrators need a controlled, auditable way to make corrections in an already-closed period.
- Permit edits to audit rows — rejected; the application makes them append-only. Database administrators with direct SQL privileges remain trusted and can bypass this application control.
