# Sprint1 Build017 — Consistency False Positive Fix

## Fixed
- False positive caused by comparing tax-included line sum against tax-excluded subtotal.
- Tokyo Koibito Excel parser now extracts subtotal/tax/total more reliably.
- Compare Engine now focuses on reliable business fields.

## Added
- Business-readable `business_review.xlsx`.
- Error folder now includes `business_review.xlsx` in addition to JSON.
- Sales ledger registration only when no differences and no reconciliation errors.

## Business rule
- Consistent PDF/Excel -> register to Sales Ledger.
- Inconsistent PDF/Excel -> route to Error folder with readable review report.
