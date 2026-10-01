# Financial Period-Close Runbook

This runbook describes an operator-controlled close for one TrackWise business. It supplements, but does not replace, the business's accounting policies, independent review, tax filings, or jurisdiction-specific requirements.

## Roles and controls

- Assign a preparer and an independent reviewer. Use an `admin` or `accountant` account to close a period.
- Only an `admin` can reopen a period. Reopening requires an explicit confirmation in the Period Close screen and is recorded in the application audit log.
- Record the business, period end date, preparer, reviewer, approval, completion time, and backup identifier in the organization's controlled close evidence.
- Do not share accounts or put credentials, database URLs, or unredacted financial data in the close evidence.

The application close date is a business-scoped posting boundary. It rejects financial records and edits dated on or before the boundary. The close action only advances that date; it does not automatically post closing journals, close nominal accounts, certify statements, or create a statutory filing.

## Before closing

1. Confirm the correct business and reporting period. Identify any open prior-period issues and the intended close-through date.
2. Complete entry and review of the period's sales, receipts, purchases, expenses, payments, journals, and other source documents. Resolve duplicates, omissions, and items posted to the wrong date or account.
3. Reconcile bank and cash accounts to statements through the period end. Investigate and document every material unreconciled difference.
4. Review receivables, payables, inventory quantities and valuation, and other relevant balance-sheet accounts against their supporting records. Post approved accruals, corrections, and adjustments before the close.
5. Review the trial balance. Confirm total debits equal total credits and investigate unusual balances, suspense accounts, and material period-to-period changes.
6. Review the income statement, balance sheet, cash flow, and other reports required by the business's close checklist. Retain dated copies or other controlled evidence outside the application as required.
7. Run the accounting integrity check for the business. An authenticated operator can use the Accounting verification page/API documented in [Operations](OPERATIONS.md). Resolve failures before closing; a balanced trial balance alone does not establish that the underlying records are complete or correct.
8. Take a production database backup and verify that it is readable. Follow [Backup and Retention](BACKUP_AND_RETENTION.md); record the backup identifier in the close evidence.
9. Obtain the required independent review and approval. Do not close while material exceptions remain unexplained.

## Close the period

1. Sign in to the intended business using an authorized `admin` or `accountant` account.
2. Open **Accounting → Journal Entries → Period Close**.
3. Confirm the displayed current close date and enter the final date reviewed. The date cannot be in the future and must be later than the current close-through date.
4. Recheck the business and date, then submit the close.
5. Verify that the Period Close screen displays the new boundary. Confirm that a test or operationally appropriate attempt to post/edit a transaction dated on or before the boundary is rejected; do not create test transactions in production merely to perform this check.
6. Record the resulting date, operator, reviewer approval, reports, integrity-check result, and backup identifier in the close evidence. Notify affected staff that prior dates are locked.

The control is cumulative: when a date is closed, dates on or before it are locked. Move the boundary forward one approved period at a time.

## Corrections after closing

1. Prefer correcting an error with an appropriately reasoned reversal and replacement entry dated in an open period, if that treatment is appropriate under the organization's accounting policy.
2. If a correction genuinely must be entered in the closed period, obtain documented approval from the authorized reviewer and coordinate an `admin` to reopen it. Plan the brief period of unlocked posting access.
3. In **Accounting → Journal Entries → Period Close**, an `admin` uses the reopen action and confirms it. Reopening clears the close-through date; it does not reopen only a selected month. Treat all dates as unlocked until the period is closed again.
4. Complete only the approved corrections. Retain the reasons, supporting documents, approver, user, and timestamps. The application records the reopen in the audit log; verify the corresponding audit evidence.
5. Repeat the applicable reconciliations, integrity check, report review, independent approval, and backup steps above. Close through the newly reviewed date again and verify the boundary.

If an unintended reopen occurs, stop period-dated posting, notify the business administrator, assess changes made while unlocked, and re-close only after review. Do not directly edit the database close-date field.

## Completion checklist

- [ ] Correct business and date range confirmed
- [ ] Source transactions entered and reviewed
- [ ] Bank/cash, receivables, payables, inventory, and relevant balance-sheet accounts reconciled
- [ ] Trial balance and required financial reports reviewed; exceptions documented
- [ ] Accounting integrity check passed
- [ ] Verified backup recorded
- [ ] Independent approval retained
- [ ] Close-through date verified in TrackWise
- [ ] Close evidence stored in the approved, access-controlled location
