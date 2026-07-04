# Build014 Test Plan

## Gate 1 — Unit tests
Run:

```powershell
.\scripts\request-smoke-test.ps1
```

Expected:
- pytest passes
- Python source compilation passes

## Gate 2 — Duplicate protection
1. Run the same PDF/Excel pair twice.
2. First run must be `OK`.
3. Second run must be `SKIPPED_DUPLICATE`.
4. Run with `-Force`; pair must process again.

## Gate 3 — Failure isolation
1. Add one invalid/corrupt file pair.
2. Add one valid pair.
3. Run stable batch.
4. Invalid pair must create `_failed\*.error.json`.
5. Valid pair must still complete.

## Gate 4 — Output
Each successful job must include:
- pdf.json
- excel.json
- differences.json
- reconciliation.json
- acceptance_score.json
- differences.xlsx
- differences.html

## Gate 5 — Pilot decision
No Pilot release if:
- smoke tests fail
- duplicate protection fails
- one corrupt pair stops the entire batch
- acceptance score cannot be reviewed
