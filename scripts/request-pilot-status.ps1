$OutputDir="Y:\TLC-BOS\Documents\RequestEmployee\Output"
$Summary=Join-Path $OutputDir "batch_stable_summary.json"
Write-Host "Request Employee Pilot Status"
if (Test-Path $Summary) { Get-Content $Summary -Encoding UTF8 } else { Write-Host "No batch_stable_summary.json found." }
