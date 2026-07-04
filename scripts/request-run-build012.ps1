param(
  [Parameter(Mandatory=$true)][string]$Pdf,
  [Parameter(Mandatory=$true)][string]$Excel,
  [string]$OutputDir="Y:\TLC-BOS\Documents\RequestEmployee\Output"
)

$Root="Y:\TLC-BOS\Repository\projects\tlc-platform\apps\request-employee"
Set-Location $Root
if (!(Test-Path ".venv")) { python -m venv .venv }
. ".\.venv\Scripts\Activate.ps1"
pip install -r requirements.txt
$env:PYTHONPATH="$Root\src"

python src/tokyo_main.py `
  --pdf $Pdf `
  --excel $Excel `
  --output-dir $OutputDir
