param([Parameter(Mandatory=$true)][string]$PackageName,[string]$RunTests="true",[string]$StartApi="false")
$ErrorActionPreference="Stop"
$Repo="Y:\TLC-BOS\Repository\projects\tlc-platform";$Downloads="Y:\TLC-BOS\Downloads"
$Zip=Join-Path $Downloads $PackageName;$LiveApp=Join-Path $Repo "apps\request-employee-platform"
$Py="C:\TLC-BOS\venv\request-employee-platform\Scripts\python.exe"
$Db="C:\TLC-BOS\data\test\request_platform_test.db";$Stamp=Get-Date -Format "yyyyMMdd_HHmmss"
$Stage=Join-Path $Downloads "_TLC_STAGE_$Stamp";$BackupRoot="C:\TLC-BOS\backups\request-employee-platform"
$BackupApp=Join-Path $BackupRoot "app_$Stamp";$BackupDb=Join-Path $BackupRoot "db_$Stamp.sqlite"
if($PackageName -notmatch '^[A-Za-z0-9_.-]+\.zip$'){throw "Invalid package name"}
if(!(Test-Path $Zip)){throw "Package not found: $Zip"};if(!(Test-Path $Py)){throw "Python venv missing: $Py"}
New-Item -ItemType Directory -Force $BackupRoot|Out-Null
if(Test-Path $Stage){Remove-Item $Stage -Recurse -Force};Expand-Archive $Zip $Stage -Force
$StageApp=Join-Path $Stage "apps\request-employee-platform";if(!(Test-Path $StageApp)){throw "Invalid FULL package"}
$Preflight=Join-Path $Stage "scripts\tlc-build030r2-preflight.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Preflight -ExtractedRoot $Stage -PythonExe $Py
if($LASTEXITCODE -ne 0){throw "Preflight failed"}
if(Test-Path $LiveApp){Copy-Item $LiveApp $BackupApp -Recurse -Force};if(Test-Path $Db){Copy-Item $Db $BackupDb -Force}
$OldApp="$LiveApp.__old_$Stamp";$swapped=$false
try{
 @(8018,8020,8021,8022)|%{Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue|%{Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue}}
 if(Test-Path $LiveApp){Move-Item $LiveApp $OldApp};Copy-Item $StageApp $LiveApp -Recurse -Force;$swapped=$true
 Copy-Item (Join-Path $Stage "scripts\*") (Join-Path $Repo "scripts") -Recurse -Force
 Push-Location $LiveApp
 try{
  $env:PYTHONPATH=$LiveApp;$env:TLC_ENV="test";$env:TLC_DATABASE_URL="sqlite:///C:/TLC-BOS/data/test/request_platform_test.db"
  $env:TLC_DOCUMENT_ROOT="C:/TLC-BOS/data/test/documents";$env:TLC_LEGAL_ENTITY_DEFAULT="TEST-JP-01"
  & $Py -m pip install -r requirements.txt;if($LASTEXITCODE -ne 0){throw "Dependency install failed"}
  & $Py -c "from src.main import app; print('IMPORT OK')";if($LASTEXITCODE -ne 0){throw "Import gate failed"}
  if($RunTests -eq "true"){& $Py -m pytest -q;if($LASTEXITCODE -ne 0){throw "Tests failed"}}
  & $Py -c "from fastapi.testclient import TestClient;from src.main import app;c=TestClient(app);assert c.get('/health').status_code==200;assert c.get('/dashboard').status_code==200;assert c.get('/sales').status_code==200;print('SMOKE OK')"
  if($LASTEXITCODE -ne 0){throw "Smoke failed"}
 }finally{Pop-Location}
 if(Test-Path $OldApp){Remove-Item $OldApp -Recurse -Force}
 if($StartApi -eq "true"){Start-Process $Py -ArgumentList @("-m","uvicorn","src.main:app","--host","127.0.0.1","--port","8018") -WorkingDirectory $LiveApp}
 Write-Host "DEPLOY SUCCESS"
}catch{
 if($swapped){if(Test-Path $LiveApp){Remove-Item $LiveApp -Recurse -Force};if(Test-Path $OldApp){Move-Item $OldApp $LiveApp}elseif(Test-Path $BackupApp){Copy-Item $BackupApp $LiveApp -Recurse -Force}}
 if(Test-Path $BackupDb){Copy-Item $BackupDb $Db -Force};throw
}finally{if(Test-Path $Stage){Remove-Item $Stage -Recurse -Force}}
