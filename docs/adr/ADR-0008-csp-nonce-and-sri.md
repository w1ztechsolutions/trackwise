# ADR-0008: CSP Nonce Architecture and SRI Enforcement

**Feature:** Replace `'unsafe-inline'` CSP policy with per-request nonces and add SRI hashes to all external resources

**Why chosen:**
- MDN HTTP Observatory failed CSP test due to `'unsafe-inline'` in `script-src` and missing `object-src` restriction.
- MDN HTTP Observatory failed SRI test because external scripts lacked `integrity` attributes.
- `'unsafe-inline'` nullifies XSS protections; removing it requires all inline scripts to carry a nonce or hash.
- Inline event handlers (`onclick`, `onchange`, etc.) and Jinja2-rendered inline scripts produce per-request or dynamic content, making static hashes impractical.
- Per-request nonces allow specific inline scripts without opening the door to arbitrary injection.

**Strengths:**
- CSP score passes MDN Observatory without requiring a full rewrite of template data flows.
- SRI ensures CDN resources have not been tampered with in transit.
- Nonces are unpredictable per request, preventing injected scripts from executing.
- Externalizing scripts into `static/js/` improves cacheability and separation of concerns.

**Alternatives considered:**
- Static hashes for every inline script. Rejected because Jinja2 templates render dynamic data (e.g., `{{ chart_labels | tojson }}`), producing different HTML per request.
- Fully externalize everything including dynamic data. Rejected due to high template refactor scope and risk of breaking existing page behaviors.
- Keep `'unsafe-inline'`. Rejected because it fails the security scan and weakens XSS defense.
