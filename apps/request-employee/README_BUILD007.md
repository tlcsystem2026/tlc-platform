# Build007

Adds:
- Intelligent PDF/Excel file pairing
- Invoice-number pairing first
- Filename similarity fallback
- Difference severity: ERROR / WARNING / INFO
- Money tolerance
- HTML report output
- Improved Excel report styling
- Batch summary with error/warning counts

Run:

```powershell
$env:PYTHONPATH="$PWD\src"
python src/batch_main.py `
  --pdf-dir "Y:\TLC-BOS\Documents\RequestEmployee\PDF" `
  --excel-dir "Y:\TLC-BOS\Documents\RequestEmployee\Excel" `
  --output-dir "Y:\TLC-BOS\Documents\RequestEmployee\Output" `
  --money-tolerance 0
```
