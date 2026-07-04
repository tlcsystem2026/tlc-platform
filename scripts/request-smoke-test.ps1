$ErrorActionPreference = "Stop"
$Root = "Y:\TLC-BOS\Repository\projects\tlc-platform\apps\request-employee"
Set-Location $Root

if (!(Test-Path ".venv")) { python -m venv .venv }
. ".\.venv\Scripts\Activate.ps1"
pip install -r requirements.txt
$env:PYTHONPATH = "$Root\src"

Write-Host "Running unit tests..."
pytest -q

Write-Host "Compiling Python sources..."
python -m compileall -q src

Write-Host "Smoke test PASSED."
