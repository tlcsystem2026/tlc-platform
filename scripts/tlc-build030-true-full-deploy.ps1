$ErrorActionPreference = "Stop"
$Repo = "Y:\TLC-BOS\Repository\projects\tlc-platform"
$Zip  = "Y:\TLC-BOS\Downloads\TLC_BUILD030_true_full_request_platform_FULL.zip"
$Temp = "Y:\TLC-BOS\Downloads\_TEMP_BUILD030"
$App  = "$Repo\apps\request-employee-platform"
$Venv = "C:\TLC-BOS\venv\request-employee-platform"
$Py   = "$Venv\Scripts\python.exe"
@(8018,8020,8021,8022) | ForEach-Object { Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }
if (Test-Path $Temp) { Remove-Item $Temp -Recurse -Force }
Expand-Archive -Path $Zip -DestinationPath $Temp -Force
Copy-Item -Path "$Temp\*" -Destination $Repo -Recurse -Force
Remove-Item $Temp -Recurse -Force
if (!(Test-Path $Py)) { New-Item -ItemType Directory -Force "C:\TLC-BOS\venv" | Out-Null; python -m venv $Venv }
& $Py -m pip install --upgrade pip
& $Py -m pip install -r "$App\requirements.txt"
cd $App
$env:PYTHONPATH = $App
$env:TLC_ENV = "test"
$env:TLC_DATABASE_URL = "sqlite:///C:/TLC-BOS/data/test/request_platform_test.db"
$env:TLC_DOCUMENT_ROOT = "C:/TLC-BOS/data/test/documents"
$env:TLC_LEGAL_ENTITY_DEFAULT = "TEST-JP-01"
& $Py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Build030 tests failed." }
& $Py -m uvicorn src.main:app --host 127.0.0.1 --port 8018
