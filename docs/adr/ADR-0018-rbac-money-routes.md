# ADR-0018: Role-Based Access Control on Money Routes

**Feature:** Financial write paths enforce the staff role; read pages stay
open to all logged-in staff.

**Why chosen:**
> The retailer workflow audit found RBAC missing on critical routes: any
> logged-in user (a viewer, a storekeeper) could POST a sale, issue an
> invoice, void it, or pay a supplier. The permission system
> (`app/auth/permissions.py`, `role_required`) existed and guarded the
> accounting blueprint, but the sales / purchases / payments blueprints
> never adopted it.

**Decision:**
- New decorator `mutation_role_required(*roles)` (app/auth/decorators.py):
  enforces roles on MUTATING methods only (POST/PUT/PATCH/DELETE); GET
  pages pass through, so no read page or navigation link breaks.
  Denial is a flash + redirect instead of a bare 403, because these are
  browser form submissions — the user sees why the action was refused.
- Policy matrix applied to the money routes:

  | Action | Allowed roles |
  |---|---|
  | Walk-in sale (POST /sales) | admin, manager, cashier |
  | Issue credit invoice (POST /invoices), send | admin, manager |
  | Void / mark paid / apply payment / credit notes | admin, manager, accountant |
  | Customer CRUD | edit: admin, manager; create: admin, manager, accountant; delete: admin, manager |
  | Create purchase (goods in) | admin, manager, storekeeper |
  | Record supplier / expense payment (POST /payments) | admin, manager, accountant |
  | Supplier CRUD | create/edit: admin, manager, storekeeper; delete: admin, manager |

- The mapping matches the existing `PERMISSIONS` design intent (cashier
  = counter sales, storekeeper = goods-in, accountant = books, manager =
  day-to-day owner delegate, admin = everything).
- `LOGIN_DISABLED` bypass mirrors `role_required`, so the automated test
  suite (LOGIN_DISABLED=True) is unaffected; RBAC tests run a separate
  app instance with LOGIN_DISABLED=False.

**Strengths:**
- Surgical: zero behavior change for reads; only the audited money
  mutations are gated.
- Reusable decorator keeps policy declarative at each route.
- Aligned with the Malawian SME staffing reality: one owner (admin), a
  shop attendant (cashier), a stock clerk (storekeeper), an external
  bookkeeper (accountant).

**Alternatives considered:**
- Apply `role_required` to whole blueprints — rejected: it would 403 the
  GET pages too and break navigation for read-only staff.
- Fine-grained `has_permission` names per action — deferred: the
  `PERMISSIONS` map lacks names for invoice lifecycle ops; introducing
  them is a larger change with no immediate functional gain over role
  sets.
- API-key routes — out of scope: the public API (`api/`) authenticates
  via the app API key, which is an integration credential, not a staff
  role.
