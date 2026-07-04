# Sprint1 Build011

## Delivered
- Parser diagnostics JSON for each PDF/Excel parse
- Batch-level parser diagnostics JSON
- Batch-level parser diagnostics Excel
- Output validation foundation
- Improved Tokyo Koibito PDF extraction tolerance

## Purpose
Before further parser tuning, we need visibility into what is extracted correctly and what is missing. This build creates the diagnostic layer.

## Review files
For each request output folder:
- `pdf_diagnostics.json`
- `excel_diagnostics.json`

At output root:
- `parser_diagnostics.json`
- `parser_diagnostics.xlsx`

## Next Build012
- Use diagnostics to tune Excel and PDF field extraction.
- Add raw extracted text export for parser debugging.
- Add business acceptance scoring.
