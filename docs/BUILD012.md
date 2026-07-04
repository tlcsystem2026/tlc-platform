# Sprint1 Build012 — Real Data Calibration

## Delivered
- PDF raw extracted text export: `pdf_raw.txt`
- Excel raw cell export: `excel_cells.csv`
- Business acceptance scoring: `acceptance_score.json`
- Acceptance grades:
  - `PILOT_READY`
  - `REVIEW`
  - `NOT_READY`
- Build012 run script
- Acceptance scoring unit test

## Why this build matters
Build012 makes parser errors observable. Instead of guessing why a field is missing, reviewers can inspect:
- exact PDF text extracted by pdfplumber
- exact Excel cell coordinates and values
- machine-generated readiness score

## Required review
Run against the real LY01006 and LY01014 pairs and inspect:
- request number
- request date
- customer
- total amount
- line count
- false differences

## Next Build013
- Tax 8%/10% cross-check
- subtotal/tax/total reconciliation
- parser failure vs real business difference classification
- stronger line matching
