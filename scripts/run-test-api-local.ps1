$ErrorActionPreference = "Stop"
$App = Join-Path $PSScriptRoot "..\apps\request-employee-platform"
$Venv = "C:\TLC-BOS\venv\request-employee-platform"
if (-not (Test-Path "$Venv\Scripts\python.exe")) {
  python -m venv $Venv
}
& "$Venv\Scripts\python.exe" -m pip install -r "$App\requirements.txt"
Push-Location $App
& "$Venv\Scripts\python.exe" -m pytest -q
& "$Venv\Scripts\python.exe" -m uvicorn src.main:app --host 127.0.0.1 --port 8018
Pop-Location
