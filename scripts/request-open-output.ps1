$OutputDir = "Y:\TLC-BOS\Documents\RequestEmployee\Output"
if (Test-Path $OutputDir) {
  explorer $OutputDir
} else {
  Write-Host "Output directory not found: $OutputDir"
}
