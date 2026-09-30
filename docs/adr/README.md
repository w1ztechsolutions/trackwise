# Architecture Decision Records

## Recent decisions

- [ADR-0009: Financial Audit and Period Controls](ADR-0009-financial-audit-and-period-controls.md)
- [ADR-0010: Time-Based Revenue Recognition Schedules](ADR-0010-time-based-revenue-recognition.md)
- [ADR-0011: Isolated Role-Based Demo Access](ADR-0011-isolated-role-based-demo-access.md)
- [ADR-0012: Fresh Demo Database Bootstrap](ADR-0012-fresh-demo-database-bootstrap.md)

## ADR-0001: ProductionConfig SECRET_KEY as Class Attribute

**Feature:** Add `SECRET_KEY` class attribute to `ProductionConfig` in `config.py`

**Why chosen:**
- Flask sessions require `app.secret_key` to be set.
- `DevelopmentConfig` already had `SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(32).hex())`.
- Your `.env` sets `FLASK_ENV=production`, which activates `ProductionConfig`.
- Unlike `DevelopmentConfig`, `ProductionConfig` had no `SECRET_KEY` class attribute — it only validated in `__init__`, which `app.config.from_object()` never calls.

**Strengths:**
- Sessions initialize correctly in all environments.
- Production still crashes immediately if `SECRET_KEY` is missing, preventing silent insecure deployments.

**Alternatives considered:**
- Relying solely on `__init__` validation. Rejected because `from_object()` bypasses `__init__`.
- Hardcoding a key. Rejected as a security risk.

---

## ADR-0002: Rename Public Registration to Admin-Created User Flow

**Feature:** Replace `auth.register` endpoint with `auth.create_user` (`/users/create`)

**Why chosen:**
- Public self-registration was removed to enforce business-level user creation.
- Only authenticated admins with `manage_settings` permission can create users.
- New users receive `must_change_password=True` to force password reset on first login.

**Strengths:**
- Centralized user lifecycle management.
- Reduces unauthorized account creation risk.
- Admin controls role assignment at creation time.

**Alternatives considered:**
- Keeping public registration with email verification. Rejected because business admins need to control access per tenant.
- Invite-link flow. Could be added later as an enhancement.

---

## ADR-0003: Superadmin Blueprint Templates in Blueprint Folder

**Feature:** Store superadmin templates in `app/superadmin/templates/` rather than root `templates/`

**Why chosen:**
- Flask Blueprint documentation recommends placing templates in a `templates/` subfolder inside the blueprint package.
- The `superadmin_bp` Blueprint is initialized with `template_folder='templates'`.
- Keeps admin portal templates logically grouped with their routes.

**Strengths:**
- Cleaner project structure.
- Avoids template name collisions between main app and superadmin.
- Easier to locate and maintain admin-specific views.

**Alternatives considered:**
- Root `templates/` folder for all templates. Rejected due to mixing concerns as the app grows.

---

## ADR-0004: Add `flask create-superadmin` CLI Command

**Feature:** Flask CLI command `create-superadmin` for seeding platform administrators

**Why chosen:**
- No existing mechanism to create superadmin users.
- Superadmin users are platform-level and must exist before any business can be created.
- Provides a repeatable, scriptable way to bootstrap the platform.

**Strengths:**
- Works without a separate seed script.
- Integrates with existing Flask app context.
- Validates duplicate emails before creation.

**Alternatives considered:**
- Manual database insertion. Rejected due to error-proneness and lack of password hashing.
- Separate `seed.py` script. Kept for demo data but not ideal for superadmin-only creation.

---

## ADR-0005: Responsive KPI Card Grid with `auto-fit`

**Feature:** Change `.kpi-grid` from fixed 5-column layout to `repeat(auto-fit, minmax(180px, 1fr))`

**Why chosen:**
- Fixed 5-column layouts cause cards to shrink unreadably when financial figures grow (e.g., "MWK 12,450,000").
- `auto-fit` allows cards to naturally wrap to new rows based on available width.
- `minmax(180px, 1fr)` ensures cards never become too small to read.

**Strengths:**
- Future-proof for large numbers and currency formatting.
- Better mobile experience (cards stack on narrow screens).
- Fewer media query breakpoints needed.

**Alternatives considered:**
- More fixed breakpoints (3 columns → 2 columns → 1 column). Rejected because `auto-fit` handles all widths smoothly.

---

## ADR-0006: Superadmin Mobile Hamburger Navigation

**Feature:** Add hamburger toggle, overlay backdrop, and slide-in sidebar for superadmin pages

**Why chosen:**
- Superadmin used a fixed 240px sidebar with no mobile adaptation.
- On phones, the sidebar permanently consumed screen width or overlapped content invisibly.
- The main app already had a mobile sidebar pattern, but superadmin did not.

**Strengths:**
- Consistent UX across main app and superadmin.
- Sidebar slides in from left with z-index layering and overlay to dismiss.
- No permanent layout shift on desktop; toggle only appears on `max-width: 768px`.

**Alternatives considered:**
- Bottom navigation bar for mobile. Rejected because superadmin has too many menu items for a bottom bar.

---

## ADR-0007: CSP Header Update for CDN Dependencies

**Feature:** Extend `Content-Security-Policy` to allow `cdn.jsdelivr.net` styles and `cdn.vercel-insights.com` scripts

**Why chosen:**
- Superadmin templates load Bootstrap CSS and Bootstrap Icons from `cdn.jsdelivr.net`.
- Pages were rendering without styles because CSP blocked external stylesheets.
- Vercel Web Analytics script was also being blocked.

**Strengths:**
- Fixes visual regression on superadmin pages.
- Maintains security posture by still blocking inline styles and unsafe eval.

**Alternatives considered:**
- Hosting Bootstrap CSS locally. Rejected due to increased bundle size and maintenance overhead.

---

## ADR-0008: CSP Nonce Architecture and SRI Enforcement

**Feature:** Replace `'unsafe-inline'` CSP policy with per-request nonces and add SRI hashes to all external resources

**Why chosen:**
- MDN HTTP Observatory flagged CSP failure due to `'unsafe-inline'` in `script-src` and missing `object-src` restriction.
- MDN HTTP Observatory flagged SRI failure because external scripts lacked `integrity` attributes.
- `'unsafe-inline'` nullifies XSS protections; removing it requires all inline scripts to carry a nonce or hash.
- Inline event handlers and Jinja2-rendered inline scripts produce per-request or dynamic content, making static hashes impractical.
- Per-request nonces allow specific inline scripts without opening the door to arbitrary injection.

**Strengths:**
- CSP passes MDN Observatory without requiring a full rewrite of template data flows.
- SRI ensures CDN resources have not been tampered with in transit.
- Nonces are unpredictable per request, preventing injected scripts from executing.
- Externalizing scripts into `static/js/` improves cacheability and separation of concerns.

**Alternatives considered:**
- Static hashes for every inline script. Rejected because Jinja2 templates render dynamic data, producing different HTML per request.
- Fully externalize everything including dynamic data. Rejected due to high template refactor scope and risk of breaking existing page behaviors.
- Keep `'unsafe-inline'`. Rejected because it fails the security scan and weakens XSS defense.
