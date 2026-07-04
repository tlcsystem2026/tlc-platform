# Sprint1 Build005

## Delivered
- Real PDF text extraction with pdfplumber
- Request number/date/customer/summary extraction heuristics
- PDF table extraction heuristics
- Excel label and line-table discovery
- Shared normalization
- Header and line comparison
- Excel difference report
- CLI pipeline
- Initial tests

## Known limitations
- Field extraction is heuristic and must be calibrated against the full real sample set.
- Line matching is currently positional; product-code matching is planned next.
- OCR fallback is not yet included.
