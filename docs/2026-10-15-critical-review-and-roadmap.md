# TrackWise — Critical Review, Standards Comparison & Professionalization Roadmap

**Prepared:** 15 October 2026
**Reviewed state:** `main` @ d84103f (includes all Sept 30 – Oct 2 control-system commits)
**Aim:** Bring TrackWise to the level of Zoho Books / QuickBooks / Sage — by being the deepest Malawi-specific system, not a feature-count clone.

---

## Part 1 — Critical Review (as the code stands today)

### 1.1 What you have already achieved — verified in code

The Sept 30 self-audit rated TrackWise 7.6/10 with four critical gaps. The Oct 1–2 commits closed almost all of them, and the code confirms it:

| Sept 30 audit finding | Status now | Evidence in repo |
|---|---|---|
| No entry reversal framework | ✅ Fixed | Balanced counter-entry reversal; original retained |
| No period close / lock | ✅ Fixed | `period_service` guards closed periods; admin-only, audited reopen |
| Audit trail incomplete | ✅ Largely fixed | Transaction-level events on accounting, sales, purchasing, inventory, approvals, auth; bulk statements that bypass per-record audit events are blocked |
| AR/AP aging ignores payments | ✅ Fixed | `aging_utils.get_allocated_amounts()` subtracts receipts / approved payments as-of-date |
| No deferred revenue | ✅ Partial | Time-based straight-line deferral schedules (ADR-0010) |
| No cost centers / branches / budgets | ✅ Fixed | Cost centers + branches on journal lines; `expense_budgets`, variance reporting, XLSX budget import |
| No bank-reconciliation lock | ✅ Fixed | `BankReconciliationPeriod` per-account lock, audited match/unmatch |
| `/api/products` public | ✅ Fixed | All JSON routes now `@login_required`, business-scoped |
| Tax oversimplified | ⚠️ Only labelled | Tax shown as "estimate" from a configured flat rate; no VAT engine |
| Multi-currency | ❌ Unfixed | `Business.currency` still a single string, default `MWK` |

**Confirmed strengths:** enforced balanced entries, `Numeric(14,2)` precision, hierarchical COA + taxonomy, FIFO inventory with tests, 9-report suite (IS, BS, CF, TB, GL, cashbook, AR/AP aging, budget variance) with XLSX export, RBAC + approval workflows, multi-tenant scoping, staged and audited spreadsheet imports, isolated demo workspaces, CSP-nonce/SRI security hardening, ADRs and runbooks. This is genuinely professional discipline — the audit → fix → re-audit loop visible in the git history is something many commercial codebases never do.

### 1.2 Scorecard vs. the majors

Scored on "can a Malawian SME run its books on this and satisfy both its accountant and MRA?"

| Capability | TrackWise | QB / Zoho / Sage standard | Verdict |
|---|---|---|---|
| Double-entry engine, GL, journals | Full | Full | **Parity** |
| COA, opening balances, fiscal year | Full | Full | **Parity** |
| Period close, reversals, audit trail | Good | Good | **Near parity** |
| Financial statements | 9 reports, HTML + XLSX | PDF, email, drill-down, comparatives | **Near parity** |
| Bank reconciliation | Manual statement import, match, period lock | Automated bank feeds | **Major gap** |
| Invoicing lifecycle | Draft → issued, void, credit notes | Quote → invoice → partial payments → reminders → PDF/email | **Gap** |
| Purchasing | Bill → payment, purchase returns | PO → goods receipt → 3-way match → bill | **Gap** |
| Tax engine | Flat "estimate" rate | VAT/GST codes per line, inclusive/exclusive, filing reports, e-invoicing | **Critical gap** |
| Multi-currency | None | Core everywhere | **Critical gap (low urgency in MWK economy)** |
| Payroll | None (Staff model only) | PAYE, pension, payslips, statutory filings | **Gap — and a real Malawi need** |
| Fixed assets / depreciation | None | Asset register, schedules, disposal | **Gap (IFRS for SMEs s.17)** |
| Inventory | FIFO, multi-warehouse, production | Plus weighted-average option, barcodes | **Mostly parity for target SME** |
| Payments acceptance | Stripe | Local rails (Airtel Money, TNM Mpamba) | **Gap — Stripe is marginal in Malawi** |
| API / ecosystem | Small internal REST API | App stores, webhooks, OAuth apps, OpenAPI | **Gap (deliberate for now)** |
| Mobile | Responsive web | Native apps, receipt capture | **Gap (acceptable v1)** |
| Bank statement formats | Spreadsheet | OFX, CAMT.053, MT940 | Minor gap |
| SaaS operations | Subscriptions, superadmin, demo DB, health checks, runbooks | SOC 2 / ISO 27001 certified | **Good indie posture, uncertified** |

### 1.3 The five things I'd rank above everything else

1. **No VAT/tax engine.** The single biggest blocker to being taken seriously as accounting software in Malawi. Invoices and bills need per-line tax codes, inclusive/exclusive pricing, a VAT control account, and a VAT return report. Until then TrackWise is a ledger, not a tax-compliant bookkeeping system. Note the rate itself moved: 16.5% → **17.5% effective January 2026** (2025/26 mid-year budget review) — so the engine must be *rate-versioned by effective date*, not a single number in settings.
2. **E-invoicing is already mandatory in Malawi.** MRA phased out Electronic Fiscal Devices on 31 January 2026 and rolled out the **Electronic Invoicing System (EIS)** from 1 May 2026; VAT-registered taxpayers issue tax invoices through it, and EFD-era invoices are no longer accepted for VAT deduction. A system that can talk to (or export clean data for) the EIS is a compliance feature the majors still handle clumsily in this market. This is your strongest differentiator — see roadmap Phase 1.
3. **No automated bank feeds.** Reconciliation exists but capture is manual. Open banking barely exists in Malawi, so the pragmatic middle ground is structured statement parsing (MT940/CAMT.053/OFX), rule-based matching, and mobile-money transaction exports, not chasing TrueLayer-style integrations.
4. **Vercel serverless is a strategic ceiling.** Session-based auth, Jinja monolith, Celery forced to run synchronously per request (`CELERY_DISABLED=true`), no background workers, cold starts. Fine to a few hundred tenants; a real SaaS needs long-running hosting (Railway/Render/Fly/ECS) where Celery/Redis genuinely run. Make that decision deliberately and record it as ADR-0014.
5. **Repo hygiene and the trust gap.** `__pycache__/` is committed; `services/fifo_service.py` lives outside `app/` (two service roots). Small, but a professional repo signals care. Bigger: the majors sell trust — certifications, pen tests, 20-year track records. A single maintainer cannot win that race on features; you win it on **Malawi depth and being the software accountants in Blantyre recommend**.

### 1.4 Strategic framing

Do not chase Zoho feature-for-feature; that is a 10-year, 200-engineer race. There is already a Malawi-focused competitor doing "built around your country's rules, not adapted after the fact" (HeadOffice) — study their positioning. TrackWise's winning position:

> **The accounting system built for Malawian SMEs that is compliant with MRA requirements out of the box** — it produces the VAT return, the PAYE report, the EIS-ready invoice data, and IFRS-for-SMEs statements without the client ever exporting to Excel.

Every roadmap item below is filtered through that lens: Malawi depth first, generic parity second, enterprise features never.

---

## Part 2 — Accounting standards: what applies, and how each maps into app functionality

### 2.1 The applicable framework: IFRS for SMEs

Malawi's standard-setter, **ICAM** (Institute of Chartered Accountants in Malawi), has adopted the **IFRS for SMEs Accounting Standard** as the framework for non-publicly-accountable entities, and has published an official SME definition for eligibility (per IFRS.org's jurisdiction profile). Full IFRS applies to publicly accountable entities; most of your target market reports under IFRS for SMEs (current: third edition, 2019). That is the standard your statements should present compliance with — it is deliberately simpler than full IFRS (no deferred tax burden for most, simplified financial instruments, no IFRS 16 lease complexity).

### 2.2 Standard-by-standard mapping into TrackWise functionality

| IFRS for SMEs section | Requirement in plain terms | TrackWise today | What to build |
|---|---|---|---|
| s.2 / s.3 — Concepts & financial statement presentation; accrual basis | Statements on accrual basis; comparative period figures; going-concern assessment | Accrual postings; fiscal-year start; no comparatives | Cash/accrual basis toggle for micros; comparative columns (this year vs last) on IS and BS; going-concern note template |
| Cash flow statement (s.7 in 2nd ed.) | Cash flows classified operating / investing / financing; direct or indirect method | CF report exists (direct) | Add indirect-method view derived from journals; it is what accountants expect |
| s.13 — Inventories | Lower of cost and NRV; count adjustments; cost formulas (FIFO and weighted average both permitted) | FIFO + stock counts ✅ | NRV write-down flow (posts expense vs inventory); optional weighted-average valuation |
| s.17 — PPE | Capitalize qualifying assets; depreciate over useful life; disposals | **Missing** | **Asset register module**: register, straight-line/reducing-balance schedules, monthly auto-journal, disposal with gain/loss. High value, medium effort |
| s.20 — Leases | (3rd ed.) Single lessee model: right-of-use asset + lease liability; exemption for short-term/low-value | Missing | Low priority for the target market initially; a lease schedule template with manual journal support is enough for most SMEs |
| s.21 — Provisions & contingencies | Recognize when probable and estimable | Manual journals cover it | Optional: provision template (e.g., warranty accrual) |
| s.23 — Revenue | Recognize when performance obligation satisfied; deferred revenue for goods/services delivered later | Time-based straight-line deferral exists ✅ (ADR-0010) | Extend to milestone-based schedules for contracts; credit-sale terms/due dates already present |
| s.28 — Employee benefits | Short-term benefits recognized as incurred; defined-contribution pension | **Missing** | Payroll-lite (see Part 3 Phase 3): gross → PAYE → pension → net, payslips, payroll journal |
| s.29 — Income taxes | Current tax payable; basic deferred tax (3rd ed. gives a simplified approach) | Flat "estimate" only | Tax computation helper: taxable profit = accounting profit ± adjustments, with adjustments list; provisional tax calendar; deferred tax is optional at this scale |
| s.30 — Foreign currency | Record foreign-currency transactions at date's rate; restate balances at closing rate; FX gains/losses to P&L | **Missing (MWK only)** | Multi-currency with `CurrencyRate` table and period-end revaluation entries. Real need for importers (USD/ZAR purchases); schedule behind tax engine |
| s.33 — Related party disclosures | Disclose related-party transactions | Nothing flags them | Cheap, high-audit-value: "related party" flag on customer/supplier records + a related-party transaction report |
| s.3 presentation + notes | Notes to the statements | Reports exist as statements | Generate a notes pack (accounting policies, related parties, contingencies) as part of year-end close |

### 2.3 The Malawi statutory layer (what the software must DO)

Verified against public sources, October 2026 — re-verify each against mra.mw before building, since rates moved in Jan 2026:

| Requirement | Current facts (2026) | App functionality to build |
|---|---|---|
| **VAT** | Standard rate **17.5%** (was 16.5%; raised in 2025/26 mid-year budget review). Registration mandatory above **MK 25 million** taxable turnover in 12 months; voluntary below. Returns filed **monthly** via **Msonkho Online** | Rate-versioned tax codes (standard/zero-rated/exempt) with effective dates; per-line tax on invoices/bills; inclusive/exclusive toggle; VAT control account; **VAT return report** (output tax − input tax, per period, mapped to the MRA return layout); registration-threshold monitoring alert |
| **E-invoicing (EIS)** | EFDs ceased 31 Jan 2026; **Electronic Invoicing System** mandatory for VAT-registered taxpayers from ~1 May 2026; tax invoices must be issued through it | Investigate the EIS taxpayer API/spec; build invoice payload export (structured, immutable, with required fields) even if real-time integration comes later; keep invoices' audit chain intact |
| **Withholding tax** | Applies to payments like rent, interest, dividends, management/consultancy fees (confirm current schedule on mra.mw) | WHT codes on qualifying bill payments; certificate data capture; remittance report per WHT type |
| **PAYE** | Monthly bands (effective Jan 2026): 0% to MK 170,000; **30%** to MK 1,570,000; **35%** to MK 10,000,000; **40%** above | Payroll-lite with banded PAYE, statutory pension contributions, TEVETA training levy, payslip PDFs; monthly P12 return report and annual P16 summary mapped to MRA forms; P9 certificate data |
| **Corporate income tax** | 30% standard rate; provisional tax paid in quarterly installments | Provisional-tax calendar with reminders; taxable-profit computation helper |
| **Data Protection Act 2024** | Commenced 3 June 2024; **MACRA** is the data protection authority; registration and enforcement regime rolling out; cross-border transfer restrictions apply | As a SaaS holding customer payroll/customer data: data controller registration plan, cross-border transfer assessment (data currently hosted on Vercel/Neon infrastructure abroad), data export/deletion on request, breach notification procedure, documented retention policy |
| **Companies Act financial reporting** | SME reporting thresholds/audit exemptions determine who must file what | Keep statements capable of producing the IFRS-for-SMEs primary statements + notes; year-end close checklist in-product |

### 2.4 Where each standard lands in the architecture

The good news: your existing plumbing is the right plumbing for nearly everything above.

- **Tax engine** → new `TaxCode` / `TaxRate` models (effective-dated); line-level tax columns on invoice/bill line items; posting rule to a `VAT Control` liability account; report service reading journal lines tagged with tax codes. Per-business config; zero-rated/exempt tax codes available for unregistered micros.
- **Asset register** → `FixedAsset`, `DepreciationSchedule` models; a monthly job (Celery once you leave synchronous serverless) posts `Dr Depreciation Expense / Cr Accumulated Depreciation` per asset; disposal posts gain/loss through the existing balanced-entry service.
- **Payroll-lite** → `PayslipRun` building on the existing `Staff` model; journal posts gross expense, PAYE/pension/TEVETA liabilities, net cash; liabilities cleared on remittance payment, feeding a remittance report.
- **Multi-currency** → `CurrencyRate(date, currency, rate)`; `currency_code` + `amount_original` on journal lines; unrealized FX revaluation entries generated at period close; reporting in base currency only until then.
- **EIS readiness** → an invoice export/format service and an immutable invoice audit record (you already have both building blocks: XLSX export + audit trail).
- **Data protection** → mostly operations (retention policy, MACRA registration, transfer assessment) plus existing export/delete tooling.

---

## Part 3 — Roadmap

Sequenced for a solo maintainer with AI assistance: each phase is shippable on its own, and each moves you closer to "the compliant system accountants recommend."

### Phase 0 — Hygiene & foundations (1–2 weeks)
- Remove `__pycache__` from git; fold `services/fifo_service.py` into `app/services/` (single service root).
- Pin Python version in `requirements.txt`; run the full pytest suite in CI on every push.
- Backup/restore runbook exercised once against Neon; retention policy written (also serves the Data Protection Act posture).
- **ADR-0014: hosting decision.** Either commit to Vercel-with-known-limits or plan the move to Railway/Render/Fly where Celery runs for real. Decide before Phase 3 (payroll needs scheduled jobs).

### Phase 1 — The Malawi tax engine (the differentiator; ~4–8 weeks)
1. `TaxCode` + effective-dated `TaxRate` models; seed Malawi rates (17.5% standard from Jan 2026; keep 16.5% history for back-dated entries).
2. Per-line tax on sales invoices and bills; tax-inclusive/exclusive toggle; VAT control account posting.
3. VAT return report mapped to the MRA return structure, exportable.
4. WHT codes on rent/interest/dividends/management fees; WHT remittance report.
5. Cash vs accrual toggle for micros below the registration threshold.
6. EIS groundwork: invoice payload export (structured, complete, immutable) per the EIS spec; scope a real integration as a follow-up.

**Definition of done:** an accountant can produce a defensible VAT return for MRA from TrackWise alone, and a VAT-registered shop can demonstrate EIS-compatible invoicing.

### Phase 2 — Money-in / money-out workflows (4–6 weeks)
- Quotes/estimates → convert to invoice.
- Invoice lifecycle: partial payments, overpayments/credit balance, payment reminders, PDF render + email delivery (WeasyPrint is already a dependency — unused opportunity).
- PO → goods receipt → bill with 3-way match; approval-gated like payments.
- Recurring transactions (rent, subscriptions) with auto-draft + approval.
- Document attachments (S3-compatible storage) on bills/invoices.

### Phase 3 — Asset register + payroll-lite (6–10 weeks; needs real background jobs)
- Fixed asset register with straight-line/reducing-balance depreciation, monthly auto-journals, disposal (IFRS for SMEs s.17).
- Payroll-lite: 2026 PAYE bands, pension, TEVETA levy, payslips, payroll journal, P12/P16-oriented reports.
- Year-end close wizard: checklist-driven (depreciation posted → provisions → FX revaluation → period close → statements + notes pack).

### Phase 4 — Bank feeds & interoperability (4–8 weeks)
- Statement ingestion beyond spreadsheets: MT940, CAMT.053, OFX.
- Rule-based auto-match with tolerance + reference matching; learned suggestions.
- Public read-only API with OAuth2 client-credential access for accountants; OpenAPI spec.
- Related-party flags and report (cheap IFRS-for-SMEs s.33 win).

### Phase 5 — Multi-currency & scale (only when a paying customer needs it)
- `CurrencyRate` table, per-transaction currency, period-end revaluation entries (s.30).
- Local payment rails: research Airtel Money / TNM Mpamba merchant APIs; keep Stripe for international cards.
- Migrate off synchronous-Celery-on-Vercel if tenant count demands it.

### Cross-cutting (continuous)
- Security posture: dependency scanning, a professional pen test before marketing, Data Protection Act compliance (MACRA registration, transfer assessment, retention policy).
- Chichewa/English localization.
- **Accountant practice portal** (one login, many client businesses) — in African SME markets, accounting software spreads through accountants, not ads. This is your channel play.
- Positioning: keep the ADR/audit-trail discipline public in the repo; for a trust-driven product, visible rigor is marketing.

### What NOT to build (deliberate non-goals)
Multi-entity consolidation, stock options, IFRS 16 full lease engine, deferred tax modeling beyond the SME-simplified approach, a native mobile app (responsive web + later a PWA suffices), an app marketplace. Every one of these burns solo-maintainer time the tax engine needs.

---

## Sources
- IFRS.org jurisdiction profile — Malawi (ICAM adoption of IFRS for SMEs; SME definition)
- MRA public notices — EFD→EIS transition (EFD use ends 31 Jan 2026; EIS live 1 May 2026), mra.mw
- Malawi 2025/26 mid-year budget reporting — VAT rate 16.5% → 17.5% effective January 2026
- MRA/MRA social posts — VAT registration threshold MK 25 million; monthly filing via Msonkho Online
- Sage KB Malawi Tax Summary 2026 + payroll guides — 2026 PAYE bands (0% ≤170k; 30% ≤1.57m; 35% ≤10m; 40% above); P12/P16 forms
- MACRA gazette notices — Data Protection Act 2024 commenced 3 June 2024
- HeadOffice (headoffice.app) — Malawi-focused competitor positioning and tax guides
- TrackWise repo itself: audit report, professionalization plan, ARCHITECTURE.md, CHANGELOG.md, ADR-0008…0013

*Figures verified October 2026 against public sources; re-confirm against mra.mw and ICAM before implementation, as Malawi's rates changed in January 2026 and the EIS rollout schedule has already shifted once.*
