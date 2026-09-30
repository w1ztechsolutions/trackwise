# ADR-0011: Isolated Role-Based Demo Access

**Feature:** Let visitors create or join demo businesses in a dedicated database, selecting one of six application roles.

**Why chosen:**

- Testers need to explore each permission set without registering credentials manually.
- A separate engine, selected by a signed session context, keeps demo data away from production while allowing normal application routes and authorization to work.
- Each visit creates an independent random internal user for the visitor-selected role.
- The visitor-selected internal user is the only user-creation path in a demo workspace; business admins cannot manually create additional demo users because the demo is not intended to exercise user provisioning.
- Repeated, case-folded business names are resolved through a unique registry entry, with an explicit proceed-or-change confirmation before joining existing shared data.
- An explicit opt-in setting and demo-only database bootstrap command avoid creating demo data or targeting production during schema initialization.

**Strengths:**

- Visitors select Administrator, Manager, Accountant, Cashier, Storekeeper, or Viewer during demo entry.
- Normal email/password logins explicitly use the production database; requests under a demo session use the isolated demo database.
- Random, undisclosed passwords prevent demo identities from being used through ordinary password login.
- Demo entry and confirmation actions are CSRF-protected and rate-limited, and demo sign-ins are audit-logged.

**Alternatives considered:**

- Store demo data in production with a `is_demo` flag — rejected because it leaves public demo workflows adjacent to customer data and risks cross-tenant mistakes.
- Use one user whose role is changed on demand — rejected because visitors could overwrite each other's role, and parallel testing would not use separate user records.
- Require each visitor to invent credentials — rejected because this demo flow is intended to remove signup friction and not expose credentials.
- Create one workspace per request even for duplicate names — rejected because returning users should be offered entry to an existing named demo business.

**Operational constraint:**

Enable `DEMO_MODE_ENABLED` only with a separate demo database URL. Matching endpoint/database identities (including Neon pooler aliases) are rejected, but operators must verify the Neon project/branch themselves. Anyone who can access `/demo` can create a business or join a named demo workspace and alter its data.
