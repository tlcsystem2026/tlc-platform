$Base = "Y:\TLC-BOS\Documents\RequestEmployee"
$Folders = @(
  "$Base",
  "$Base\PDF",
  "$Base\Excel",
  "$Base\Output",
  "$Base\Archive",
  "$Base\Difference"
)

foreach ($f in $Folders) {
  if (!(Test-Path $f)) {
    New-Item -ItemType Directory -Force $f | Out-Null
    Write-Host "Created: $f"
  } else {
    Write-Host "OK: $f"
  }
}

Write-Host "RequestEmployee folder check completed."
