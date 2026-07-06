param(
  [Parameter(Mandatory=$true)][string]$PackageName,
  [switch]$SkipTests,
  [switch]$StartApi,
  [int]$PreferredPort = 8018
)
$ErrorActionPreference = "Stop"
$Repo = "Y:\TLC-BOS\Repository\projects\tlc-platform"
$DownloadDir = "Y:\TLC-BOS\Downloads"
$Zip = Join-Path $DownloadDir $PackageName
$Temp = Join-Path $DownloadDir "_TEMP_DEPLOY"
$Stage = Join-Path $DownloadDir "_STAGE_DEPLOY"
$App = Join-Path $Repo "apps\request-employee-platform"
$Venv = "C:\TLC-BOS\venv\request-employee-platform"
$Py = Join-Path $Venv "Scripts\python.exe"

if ($PackageName -notmatch '^[A-Za-z0-9_.-]+\.zip$') { throw "Invalid package name: $PackageName" }
if (!(Test-Path $Zip)) { throw "Package not found: $Zip" }
if (!(Test-Path $Repo)) { throw "Repository not found: $Repo" }

if (Test-Path $Temp) { Remove-Item $Temp -Recurse -Force }
if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }

Write-Host "=== TLC Atomic-ish Controlled Local Deploy ==="
Write-Host "Package: $PackageName"

Expand-Archive -Path $Zip -DestinationPath $Temp -Force

# Check critical files before touching repo
$Critical = @(
  "apps\request-employee-platform\src\main.py"
)
foreach ($c in $Critical) {
  if (!(Test-Path (Join-Path $Temp $c))) {
    throw "Package missing critical file: $c"
  }
}

# Copy to stage first so partially extracted files never reach repo.
New-Item -ItemType Directory -Force $Stage | Out-Null
Copy-Item -Path "$Temp\*" -Destination $Stage -Recurse -Force

# Now copy stage to repo.
Copy-Item -Path "$Stage\*" -Destination $Repo -Recurse -Force

Remove-Item $Temp -Recurse -Force
Remove-Item $Stage -Recurse -Force

Set-Location $Repo
git status --short

if (!(Test-Path $Py)) {
  New-Item -ItemType Directory -Force "C:\TLC-BOS\venv" | Out-Null
  python -m venv $Venv
}

if (Test-Path "$App\requirements.txt") {
  & $Py -m pip install --upgrade pip
  & $Py -m pip install -r "$App\requirements.txt"
}

if (-not $SkipTests) {
  Set-Location $App
  $env:PYTHONPATH = "$App"
  & $Py -m pytest -q
  if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
}

Write-Host "Deploy completed."
if ($StartApi) {
  & "$Repo\scripts\tlc-start-api-dev.ps1" -PreferredPort $PreferredPort
}
