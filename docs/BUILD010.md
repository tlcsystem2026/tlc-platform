# Sprint1 Build010

## Delivered
- Batch run PowerShell script
- Folder check / creation script
- Output open script
- Output validation tool
- Output validation PowerShell script
- Request Employee runbook
- Acceptance checklist

## Purpose
This build prepares the first structured business trial workflow.

## How to validate

1. Apply Build010 into repository.
2. Run `scripts/request-check-folders.ps1`.
3. Put real PDF/Excel pairs under `Y:\TLC-BOS\Documents\RequestEmployee`.
4. Run `scripts/request-run-batch.ps1`.
5. Run `scripts/request-validate-output.ps1`.
6. Review `differences.xlsx` and `differences.html`.

## Next Build011
- Improve PDF line extraction for Tokyo Koibito samples.
- Improve Excel field extraction.
- Add parser diagnostics report.
