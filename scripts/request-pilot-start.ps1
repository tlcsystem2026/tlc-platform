param(
  [string]$PdfDir="Y:\TLC-BOS\Documents\RequestEmployee\PDF",
  [string]$ExcelDir="Y:\TLC-BOS\Documents\RequestEmployee\Excel",
  [string]$OutputDir="Y:\TLC-BOS\Documents\RequestEmployee\Output",
  [string]$MoneyTolerance="0",
  [switch]$Force
)
$ErrorActionPreference="Stop"
$Repo="Y:\TLC-BOS\Repository\projects\tlc-platform"
& "$Repo\scripts\request-check-folders.ps1"
& "$Repo\scripts\request-preflight.ps1"
& "$Repo\scripts\request-smoke-test.ps1"
& "$Repo\scripts\request-run-stable-batch.ps1" -PdfDir $PdfDir -ExcelDir $ExcelDir -OutputDir $OutputDir -MoneyTolerance $MoneyTolerance -Force:$Force
& "$Repo\scripts\request-validate-output.ps1" -OutputDir $OutputDir
Write-Host "Pilot run completed. Review Output folder."
