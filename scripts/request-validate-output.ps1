param(
  [string]$OutputDir = "Y:\TLC-BOS\Documents\RequestEmployee\Output"
)

$Root = "Y:\TLC-BOS\Repository\projects\tlc-platform\apps\request-employee"
Set-Location $Root
. ".\.venv\Scripts\Activate.ps1"
$env:PYTHONPATH = "$Root\src"

python src/validate_output_main.py --output-dir $OutputDir
