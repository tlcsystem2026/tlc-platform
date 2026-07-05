param(
  [string]$PdfDir = "Y:\TLC-BOS\Documents\RequestEmployee\PDF",
  [string]$ExcelDir = "Y:\TLC-BOS\Documents\RequestEmployee\Excel",
  [string]$OutputDir = "Y:\TLC-BOS\Documents\RequestEmployee\Output",
  [string]$SalesLedger = "Y:\TLC-BOS\Documents\RequestEmployee\Sales\sales_ledger.xlsx",
  [string]$ErrorDir = "Y:\TLC-BOS\Documents\RequestEmployee\Error",
  [string]$MoneyTolerance = "0"
)

$ErrorActionPreference = "Stop"
$Repo = "Y:\TLC-BOS\Repository\projects\tlc-platform"
$App = "$Repo\apps\request-employee"
$Venv = "C:\TLC-BOS\venv\request-employee"
$VenvPython = "$Venv\Scripts\python.exe"

if (!(Test-Path $VenvPython)) {
  & "$Repo\scripts\request-setup-local-venv.ps1"
}

New-Item -ItemType Directory -Force (Split-Path $SalesLedger) | Out-Null
New-Item -ItemType Directory -Force $ErrorDir | Out-Null

$env:PYTHONPATH = "$App\src"

& $VenvPython "$App\src\pilot_sales_flow_main.py" `
  --pdf-dir $PdfDir `
  --excel-dir $ExcelDir `
  --output-dir $OutputDir `
  --sales-ledger $SalesLedger `
  --error-dir $ErrorDir `
  --money-tolerance $MoneyTolerance
