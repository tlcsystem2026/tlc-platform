$OutputDir="Y:\TLC-BOS\Documents\RequestEmployee\Output"
$Archive="Y:\TLC-BOS\Documents\RequestEmployee\Archive"
$Stamp=Get-Date -Format "yyyyMMdd_HHmmss"
if (!(Test-Path $Archive)) { New-Item -ItemType Directory -Force $Archive | Out-Null }
if (Test-Path $OutputDir) {
  $Target=Join-Path $Archive "Output_$Stamp"
  Move-Item $OutputDir $Target
  New-Item -ItemType Directory -Force $OutputDir | Out-Null
  Write-Host "Output moved to archive: $Target"
} else {
  Write-Host "No output folder to rollback."
}
Write-Host "Rollback completed. Original PDF/Excel files were not modified."
