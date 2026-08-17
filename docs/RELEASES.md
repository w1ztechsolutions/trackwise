# Release Process & Versioning

This document describes the TrackWise release process, versioning scheme, and checklist.

---

## Versioning Scheme

TrackWise follows [Semantic Versioning](https://semver.org/):

```
MAJOR.MINOR.PATCH
```

- **MAJOR** — Incompatible API changes or breaking behavior changes.
- **MINOR** — New features or functionality in a backward-compatible manner.
- **PATCH** — Backward-compatible bug fixes.

### Pre-release Versions

For beta/alpha releases, append a pre-release identifier:

```
1.2.0-beta.1
1.2.0-rc.1
```

### Current Version

Check `CHANGELOG.md` for the latest released version. Unreleased work is tracked under `[Unreleased]`.

---

## Release Checklist

Before cutting a release, verify all of the following:

### Code Quality

- [ ] All tests pass: `pytest`
- [ ] No linting errors: `flake8 app/ tests/` (or equivalent)
- [ ] No secrets committed (run `git secret` or manual scan)
- [ ] `requirements.txt` is up to date with pinned versions
- [ ] No debug logging or `print()` statements in production code
- [ ] No `TODO` or `FIXME` comments left in critical paths

### Documentation

- [ ] `CHANGELOG.md` `[Unreleased]` section is complete and accurate
- [ ] All new features are documented in `README.md` or relevant `docs/*.md`
- [ ] `docs/API.md` is updated if any API endpoints changed
- [ ] `docs/bugs_and_fixes.md` is current
- [ ] `docs/adr/` contains ADRs for any architecture changes in this release
- [ ] `SECURITY.md` is updated if there were security fixes
- [ ] `UPGRADE.md` is updated if there are new roadmap items
- [ ] `DEPLOY_VERCEL.md` is updated if deployment steps changed

### Database

- [ ] All migrations are tested: `flask db upgrade` on a fresh database
- [ ] No migration file modifies an already-applied production migration
- [ ] Backward-compatible migrations only (no destructive changes without data migration)
- [ ] `seed.py` works correctly if applicable

### Security

- [ ] CSP headers are current and no new external dependencies are blocked
- [ ] Rate limiting is configured appropriately
- [ ] Authentication/authorization flows are tested
- [ ] No SQL injection vectors in new queries
- [ ] No sensitive data in logs

### Testing

- [ ] Unit tests cover new features and bug fixes
- [ ] Integration tests cover new routes and API endpoints
- [ ] Manual smoke test on Vercel/staging environment
- [ ] Multi-tenant data isolation verified for new features

### Deployment

- [ ] `vercel.json` is up to date
- [ ] Environment variables are documented in `DEPLOY_VERCEL.md`
- [ ] Vercel build succeeds with current `requirements.txt`
- [ ] Health check endpoint (`/health`) returns 200
- [ ] Database migrations run successfully on production

---

## Release Procedure

### 1. Prepare the Release Branch

```bash
git checkout main
git pull origin main
git checkout -b release/vX.Y.Z
```

### 2. Finalize CHANGELOG.md

- Move all `[Unreleased]` entries to a new section:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- ...

### Changed
- ...

### Fixed
- ...
```

- Add a link to the previous version at the bottom:

```markdown
[Unreleased]: https://github.com/w1ztechsolutions/trackwise/compare/vX.Y.Z...HEAD
[X.Y.Z]: https://github.com/w1ztechsolutions/trackwise/compare/vX.Y.Z-1...vX.Y.Z
```

### 3. Update Version Strings

Update version references in:

- `app/__init__.py` health check endpoint (`'version': 'X.Y.Z'`)
- Any other hardcoded version strings

### 4. Create Pull Request

```bash
git add CHANGELOG.md docs/ README.md app/__init__.py
git commit -m "chore(release): vX.Y.Z"
git push origin release/vX.Y.Z
```

Open a PR from `release/vX.Y.Z` to `main`. Ensure CI passes and review is approved.

### 5. Merge and Tag

```bash
# Merge the PR via GitHub UI or:
git checkout main
git merge --no-ff release/vX.Y.Z
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin main --tags
```

### 6. Deploy

- Deploy to Vercel: `vercel --prod`
- Run migrations: `python scripts/run_migration.py`
- Verify `/health` endpoint
- Announce release if applicable

### 7. Post-Release

- Create a new `[Unreleased]` section in `CHANGELOG.md`
- Update `UPGRADE.md` with completed items
- Close the milestone in GitHub if used

---

## Hotfix Procedure

For critical production bugs:

1. Create a hotfix branch from the current production tag:

```bash
git checkout -b hotfix/vX.Y.Z+1 vX.Y.Z
```

2. Apply the fix and update `docs/bugs_and_fixes.md` and `CHANGELOG.md`.

3. Bump the PATCH version and create a PR.

4. Merge, tag, and deploy following the standard release procedure.

---

## Deprecation Policy

When deprecating a feature:

1. Announce deprecation in `CHANGELOG.md` with a timeline.
2. Add a deprecation warning in the code (log or UI message).
3. Document the replacement in the relevant doc.
4. Remove the feature in the next MAJOR version.

**Example:**

```markdown
### Deprecated
- `/expenses` route is deprecated. Use `/purchases/payments` instead. Will be removed in v2.0.0.
```

---

## Breaking Changes

Breaking changes must:

1. Be justified in an ADR (`docs/adr/`).
2. Include a migration guide in `docs/MIGRATION_vX_to_vY.md`.
3. Be communicated in `CHANGELOG.md` under `### Changed` or `### Removed`.
4. Be accompanied by a major version bump.

---

## Rollback Procedure

If a release causes critical issues:

1. Revert the merge commit on `main`:

```bash
git revert -m 1 <merge-commit-sha>
git push origin main
```

2. Redeploy the previous stable version to Vercel.
3. Run `git tag` to create a rollback tag if needed.
4. Document the incident in `docs/bugs_and_fixes.md`.

---

## Release Frequency

- **Patch releases** — As needed for bug fixes.
- **Minor releases** — Monthly or per major feature completion.
- **Major releases** — Quarterly or when breaking changes are required.
