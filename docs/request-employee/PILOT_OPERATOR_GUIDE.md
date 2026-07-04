# Request Employee Pilot Operator Guide

## Scope
This pilot assists manual review of request documents. It does not replace human approval.

## Daily pilot workflow
1. Put original PDF files into `Y:\TLC-BOS\Documents\RequestEmployee\PDF`.
2. Put original Excel files into `Y:\TLC-BOS\Documents\RequestEmployee\Excel`.
3. Run:
   ```powershell
   .\scripts\request-pilot-start.ps1
   ```
4. Review:
   - `differences.xlsx`
   - `differences.html`
   - `acceptance_score.json`
   - `reconciliation.json`
5. Human decides final action.

## Important rules
- Original PDF and Excel are never modified.
- Git repository stores code only, not business documents.
- Pilot output must be reviewed by a person.
- Any `PARSER_FAILURE` must be treated as system tuning issue before business action.

## When to stop pilot
Stop and rollback if:
- smoke test fails
- parser extracts wrong request number
- parser extracts wrong total amount
- batch processing stops unexpectedly
- output folder structure is missing
