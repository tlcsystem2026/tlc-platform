$ErrorActionPreference = "Stop"
$Repo = "Y:\TLC-BOS\Repository\projects\tlc-platform"
$App = Join-Path $Repo "apps\request-employee-platform"
$Py = "C:\TLC-BOS\venv\request-employee-platform\Scripts\python.exe"

if (!(Test-Path $Py)) { throw "Python venv not found. Run deploy first." }

Set-Location $App
$env:PYTHONPATH = "$App"

& $Py -m uvicorn src.main:app --host 127.0.0.1 --port 8018 --reload --reload-dir "$App\src"
