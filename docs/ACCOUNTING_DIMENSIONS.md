# Branches and cost centers

Branches and cost centers provide optional reporting dimensions for accounting
entries. Both are owned by a business and use a code that is unique within that
business.

- A journal entry can be assigned to one active branch.
- Each journal line can be assigned to one active cost center.
- Manual journal entries support both assignments; approved journal entries and
  reversals retain the same dimensions.
- Trial Balance and General Ledger can be filtered by branch and cost center.
- Existing entries and automated postings remain valid without either
  assignment. Such activity appears with an unassigned dimension in unfiltered
  reports.
- Archiving a dimension prevents new assignments but preserves historic
  reporting; restoring it makes it selectable again.

Manage dimensions from **Accounting → Branches & Cost Centers**. The database
schema change is applied with the standard Alembic upgrade command.
