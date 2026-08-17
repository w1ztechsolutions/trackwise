# AGENT.md — TrackWise Documentation Enforcement Rules

This file defines mandatory rules for all AI agents (and human contributors) working in the TrackWise repository. Every code change that fixes a bug, adds a feature, modifies behavior, or alters the system architecture **must** be reflected in the appropriate documentation file before the change is considered complete.

---

## 1. Core Principle

> **No code change is complete until its documentation is updated.**

If you fix a bug, add a feature, refactor code, change configuration, or modify the database schema, you are also responsible for updating the documentation that describes that behavior.

---

## 2. Bug Fixes → `docs/bugs_and_fixes.md`

**Rule:** Every bug fix, regardless of severity, must be logged in `docs/bugs_and_fixes.md`.

**Format for each bug entry:**

```markdown
## Bug NNN: Short descriptive title

**Date:** YYYY-MM-DD  
**Severity:** Critical / High / Medium / Low  
**Environment:** All / Production / Development / Specific

**Symptom:**
> Exact error message or observed behavior.

**Root cause:**
> Technical explanation of why the bug occurred.

**Fix:**
> What was changed to resolve the issue.

**Files changed:**
- `path/to/file.py`
- `path/to/template.html`
```

**Additional requirements:**
- If the bug fix is also a security fix, add a `**Security:**` line and consider adding an entry to `SECURITY.md` if one exists.
- If the bug fix changes user-facing behavior, update `CHANGELOG.md` under the current `[Unreleased]` section.
- Do not mark bugs as "Known limitation" without a documented workaround or ticket reference.

---

## 3. Features & Changes → `CHANGELOG.md`

**Rule:** Every feature addition, behavior change, or non-trivial refactor must be recorded in `CHANGELOG.md` under the `[Unreleased]` section.

**Categories (Keep a Changelog format):**
- `Added` — New features
- `Changed` — Changes to existing functionality
- `Deprecated` — Features that will be removed in future releases
- `Removed` — Features removed in this release
- `Fixed` — Bug fixes (cross-reference with `docs/bugs_and_fixes.md`)
- `Security` — Vulnerability fixes

**Example entry:**

```markdown
## [Unreleased]

### Added
- Manual journal entry UI at `/accounting/journal-entries/create`

### Changed
- `Payment` model renamed `payment_method` to `payment_mode`

### Fixed
- Accounting integration for supplier payments (see Bug 12)
```

**Version bumping:**
- When cutting a release, move `[Unreleased]` entries to a new version header `[X.Y.Z] - YYYY-MM-DD`.
- Follow [Semantic Versioning](https://semver.org/).

---

## 4. Architecture Decisions → `docs/adr/`

**Rule:** Any change to system architecture, database schema, external integrations, or core design patterns must be documented as an Architecture Decision Record (ADR) in `docs/adr/`.

**When to create an ADR:**
- Adding a new database table or column
- Changing a core algorithm or data flow
- Introducing a new external service or library
- Changing authentication, authorization, or multi-tenancy models
- Modifying deployment architecture
- Removing or replacing a major component

**ADR naming convention:**
```
docs/adr/ADR-NNNN-short-descriptive-title.md
```

**ADR format:**
```markdown
# ADR-NNNN: Title

**Feature:** One-line description

**Why chosen:**
> Reasoning behind the decision.

**Strengths:**
- Benefit 1
- Benefit 2

**Alternatives considered:**
- Alternative 1 — Rejected because...
- Alternative 2 — Rejected because...
```

**Update existing ADRs when:**
- The decision is reversed or superseded
- The implementation diverges significantly from the original plan

---

## 5. API Changes → `docs/API.md`

**Rule:** Any change to JSON API endpoints (add, modify, remove, deprecate) must be reflected in `docs/API.md`.

**Requirements:**
- New endpoints must include: method, path, description, authentication requirements, request/response schemas, and error codes.
- Modified endpoints must have their updated schemas and behaviors documented.
- Removed endpoints must be moved to a "Deprecated" or "Removed" section with migration guidance.
- If an endpoint's authentication status changes (e.g., from public to authenticated), this must be explicitly noted.

**Example endpoint documentation:**
```markdown
### GET /api/customers

Retrieve a list of all customers for the current business.

**Authentication:** Required

**Response:** `200 OK`

```json
[
  {
    "id": 1,
    "name": "ABC Trading",
    "email": "info@abctrading.com"
  }
]
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Customer ID |
| `name` | String | Customer name |
| `email` | String | Contact email |
```
```

---

## 6. New Routes / Pages → `README.md` and Route Maps

**Rule:** Any new Flask route or page (HTML view) must be documented.

**Requirements:**
- Add the route to the "API Endpoints" section in `README.md`.
- If the route belongs to a new blueprint, add the blueprint to the project structure diagram in `README.md`.
- If the route is a JSON API endpoint, also document it in `docs/API.md`.
- If the route is part of a new module, consider adding a section to `ARCHITECTURE.md` or creating a dedicated doc in `docs/`.

---

## 7. Database Schema Changes → `docs/adr/` and Migration Files

**Rule:** Any change to the database schema (new table, new column, renamed column, removed column, index change) must be:

1. Documented in an ADR (`docs/adr/`) explaining the rationale.
2. Implemented as an Alembic migration in `migrations/versions/`.
3. Mentioned in `CHANGELOG.md` under `[Unreleased] → Added/Changed`.

**Requirements:**
- Migration files must have descriptive names (e.g., `20260817_add_bank_statements.py`).
- Never alter existing migration files that have been applied to production.
- Backfill columns with safe defaults using `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.
- For destructive changes, create a separate data migration script and document the rollback procedure.

---

## 8. Environment Variables → `.env.example` and `DEPLOY_VERCEL.md`

**Rule:** Any new environment variable, or change to an existing one, must be:

1. Added to `.env.example` with a descriptive comment.
2. Documented in `DEPLOY_VERCAL.md` (for Vercel-specific variables) or `config.py` (with inline comments).
3. Mentioned in `CHANGELOG.md` if it requires user action.

**Example `.env.example` entry:**
```env
# New Feature: Bank reconciliation
BANK_RECONCILIATION_ENABLED=true
```

---

## 9. Dependency Changes → `requirements.txt` and `CHANGELOG.md`

**Rule:** Adding, removing, or upgrading a Python package must be:

1. Reflected in `requirements.txt` with pinned versions.
2. Mentioned in `CHANGELOG.md` under `[Unreleased] → Added` (new dependency) or `Changed` (version bump).
3. If the dependency has security implications, add a note in `SECURITY.md`.

---

## 10. Security Fixes → `docs/bugs_and_fixes.md` and `SECURITY.md`

**Rule:** Security vulnerabilities must be documented in both `docs/bugs_and_fixes.md` and `SECURITY.md`.

**Requirements:**
- In `bugs_and_fixes.md`, use severity `Critical` or `High` and include the CVE or advisory reference if applicable.
- In `SECURITY.md`, add a "Security Updates" section with the fix description and recommended user action.
- Never publish detailed exploit steps. Focus on the vulnerability class and the fix.

---

## 11. Breaking Changes → Migration Guide

**Rule:** Any change that breaks backward compatibility (API contract change, database schema change, config change, behavior change) must include a migration guide.

**Migration guide requirements:**
- Create a new file in `docs/` (e.g., `docs/MIGRATION_v1.1_to_v1.2.md`).
- Document what changed, why, and step-by-step instructions for users to update.
- Include SQL migrations or data backfill scripts if needed.
- Link the migration guide from `CHANGELOG.md` and `README.md`.

---

## 12. No Documentation in `.gitignore`

**Rule:** Documentation files must be tracked by git.

**Requirements:**
- The `.gitignore` file must **not** contain `/docs/` or any pattern that ignores documentation.
- All files in `docs/`, root-level `.md` files, and this `AGENT.md` file must be tracked by git.
- If a new documentation directory is created (e.g., `docs/guides/`), ensure it is not ignored.

---

## 13. AI Agent Self-Checklist

Before completing any task, an AI agent must verify:

- [ ] If I fixed a bug, is it in `docs/bugs_and_fixes.md`?
- [ ] If I added/changed a feature, is it in `CHANGELOG.md`?
- [ ] If I changed architecture, is there an ADR in `docs/adr/`?
- [ ] If I changed the API, is `docs/API.md` updated?
- [ ] If I added a route, is it in `README.md`?
- [ ] If I changed the database schema, is there a migration and an ADR?
- [ ] If I added/changed an env var, is `.env.example` updated?
- [ ] If I added/changed a dependency, is `requirements.txt` updated?
- [ ] If it was a security fix, is `SECURITY.md` updated?
- [ ] If it was a breaking change, is there a migration guide?
- [ ] Are all documentation files tracked by git (no `.gitignore` violations)?

---

## 14. Documentation Review Standards

- **Clarity:** Use simple, direct language. Avoid jargon where possible.
- **Completeness:** Include examples, code snippets, and expected outputs.
- **Accuracy:** Verify that documented endpoints, config values, and commands match the actual code.
- **Consistency:** Use the same terminology across all docs (e.g., "business_id" not "business ID").
- **Links:** All internal links must be relative and functional. External links must use HTTPS.

---

## 15. Enforcement

- **Pre-commit hook (recommended):** Add a pre-commit hook that checks for documentation updates when code files change.
- **PR review:** All pull requests must be reviewed for documentation completeness.
- **CI check (recommended):** Add a CI job that verifies `docs/` is tracked by git and that `CHANGELOG.md` is updated when code changes.

---

## 16. Exceptions

- **Trivial changes** (typo fixes, whitespace, comment-only changes) do not require documentation updates.
- **Experimental / throwaway code** in feature branches does not require documentation until merged to `main`.
- **Hotfixes** must still update `bugs_and_fixes.md` and `CHANGELOG.md` — these are non-negotiable.

---

## Related Files

- `docs/bugs_and_fixes.md` — Bug fix log
- `CHANGELOG.md` — Version history
- `docs/adr/README.md` — Architecture Decision Records
- `docs/API.md` — JSON API documentation
- `DEPLOY_VERCEL.md` — Deployment guide
- `CONTRIBUTING.md` — Contribution guidelines
- `SECURITY.md` — Security policy (create if missing)
- `README.md` — Project overview and quick start
