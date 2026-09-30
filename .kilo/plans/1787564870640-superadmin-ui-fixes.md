# Superadmin UI/UX Fix Plan

Fix 30+ Vercel Web Interface Guidelines violations across 7 templates and 1 JS file.

## Scope
All files in `app/superadmin/templates/` + `static/js/sa-sidebar.js`.

## Approach
Fix shared layout issues globally in `sa_base.html` (affects all pages), then fix page-specific issues per template.

---

## Task 1: sa_base.html — shared layout fixes

Add to `<html>` or `<head>`:
- `color-scheme: dark` on `<html>` (fixes scrollbar/inputs in dark theme)
- `<meta name="theme-color" content="#1a1a2e">`
- `<link rel="preconnect" href="https://cdn.jsdelivr.net">` and for Bootstrap Icons domain
- Skip link: `<a href="#main-content" class="skip-link">Skip to content</a>` with `.skip-link` CSS (visually hidden until focused)

In `<style>`:
- Add `:focus-visible` styles for `.sidebar .nav-link` (ring/outline)
- Add `:focus-visible` styles for `.sa-toggle` button
- Add `:focus-visible` styles for `.logout-btn`
- Wrap flash messages container in `<div aria-live="polite">`

In HTML:
- Add `onkeydown` handler to `#saSidebarToggle`: open on Enter/Space
- Add `tabindex="-1"` to `#saSidebarOverlay` (optional but good practice)

---

## Task 2: sa_login.html — standalone login page

In `<head>`:
- Add `color-scheme: dark` on `<html>`
- Add `<meta name="theme-color" content="#0f172a">`
- Add `prefers-reduced-motion` block that disables transitions/animations

In HTML:
- Add `aria-hidden="true"` to `.brand-icon i`
- Add `spellcheck="false"` to email input (`sa_login.html:162`)

In `<style>`:
- Add `:focus-visible` styles for `.form-control` and `.btn-login`
- Add `font-variant-numeric: tabular-nums` to any numeric elements (if any)

---

## Task 3: sa_dashboard.html

In `<style>` (or rely on base if global focus styles added):
- Ensure action buttons have `:focus-visible` styles

In HTML:
- Add `aria-hidden="true"` to decorative stat card icons (`sa_dashboard.html:11`, `21`, `29`)
- Add `font-variant-numeric: tabular-nums` to stat number `<h2>` elements
- Add `text-truncate` or `truncate` class + `min-w-0` on business name cell (`sa_dashboard.html:59`)
- Add skip link (or inherit from base)

---

## Task 4: sa_businesses.html

In HTML:
- Add `text-truncate` + `min-w-0` on business name cell (`sa_businesses.html:27`)
- Add skip link (or inherit from base)

In `<style>`:
- Add `:focus-visible` styles for action buttons

---

## Task 5: sa_business_form.html

In HTML:
- Add `autocomplete="off"` to name input (`sa_business_form.html:16`)
- Add `autocomplete="off"` to tax_id input (`sa_business_form.html:20`)

In `<style>`:
- Add `:focus-visible` styles for `.form-control` and `.form-select`

---

## Task 6: sa_admins.html

In HTML:
- Add `text-truncate` + `min-w-0` on email cell (`sa_admins.html:30`)
- Add skip link (or inherit from base)

In `<style>`:
- Add `:focus-visible` styles for action buttons

---

## Task 7: sa_admin_form.html

In HTML:
- Add `autocomplete="name"` to name input (`sa_admin_form.html:16`)
- Add `autocomplete="email"` + `spellcheck="false"` to email input (`sa_admin_form.html:20`)
- Add `autocomplete="new-password"` to password input (`sa_admin_form.html:24`)
- Add `autocomplete="new-password"` to confirm_password input (`sa_admin_form.html:29`)
- Add `aria-describedby="password-hint"` to password input, and `id="password-hint"` to hint text (`sa_admin_form.html:25`)

In `<style>`:
- Add `:focus-visible` styles for `.form-control`

---

## Task 8: sa_users.html

In HTML:
- Add `text-truncate` + `min-w-0` on email cell (`sa_users.html:24`)
- Add `text-truncate` + `min-w-0` on business name cell (`sa_users.html:25`)
- Add skip link (or inherit from base)

In `<style>`:
- Add `:focus-visible` styles for action buttons (if any added later)

---

## Task 9: static/js/sa-sidebar.js

- Add `keydown` handler on `#saSidebarToggle`: toggle sidebar on Enter/Space (matches Task 1 HTML handler, but JS ensures it works even if HTML handler fails)
- Add focus trap: when sidebar opens, focus first nav link; when closes via overlay, return focus to toggle button
- Add `inert` attribute to main content when sidebar is open (improves screen reader experience)

---

## Validation

1. Open each superadmin page in browser (login, dashboard, businesses, business form, admins, admin form, users)
2. Tab through all interactive elements — verify visible focus rings
3. Test with keyboard only (no mouse) — verify navigation and form submission
4. Test mobile viewport (<768px) — verify sidebar toggle and overlay
5. Run existing test suite to confirm no regressions

---

## Out of Scope

- Route/backend changes (no new endpoints needed)
- Content copy changes
- Dark mode toggle / light theme support
- Virtualization for large tables (not yet >50 items per page)
- Internationalization / locale formatting changes
