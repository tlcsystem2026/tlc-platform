# Build008

This build adds Tokyo Koibito specific parsers and PostgreSQL repository layer.

## Tokyo Koibito single-pair run

```powershell
cd Y:\TLC-BOS\Repository\projects\tlc-platform\apps\request-employee
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH="$PWD\src"

python src/tokyo_main.py `
  --pdf "Y:\TLC-BOS\Documents\RequestEmployee\PDF\東京恋人請求書_税込_LY01006_1230_新川_取消.pdf" `
  --excel "Y:\TLC-BOS\Documents\RequestEmployee\Excel\東京恋人請求書_税込_LY01006_1230_新川_取消.xlsx" `
  --output-dir "Y:\TLC-BOS\Documents\RequestEmployee\Output"
```

## Database

Apply:

```powershell
psql -h localhost -U tlc -d tlc_platform -f database/schema/005_request_employee_tables.sql
```
