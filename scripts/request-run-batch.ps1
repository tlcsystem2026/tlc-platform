param(
  [string]$PdfDir = "Y:\TLC-BOS\Documents\RequestEmployee\PDF",
  [string]$ExcelDir = "Y:\TLC-BOS\Documents\RequestEmployee\Excel",
  [string]$OutputDir = "Y:\TLC-BOS\Documents\RequestEmployee\Output",
  [string]$MoneyTolerance = "0"
)

$Root = "Y:\TLC-BOS\Repository\projects\tlc-platform\apps\request-employee"
Set-Location $Root

if (!(Test-Path ".venv")) {
  python -m venv .venv
}

. ".\.venv\Scripts\Activate.ps1"
pip install -r requirements.txt
$env:PYTHONPATH = "$Root\src"

python src/batch_main.py `
  --pdf-dir $PdfDir `
  --excel-dir $ExcelDir `
  --output-dir $OutputDir `
  --money-tolerance $MoneyTolerance
