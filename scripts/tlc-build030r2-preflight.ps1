param([string]$ExtractedRoot,[string]$PythonExe)
$ErrorActionPreference="Stop"
$App=Join-Path $ExtractedRoot "apps\request-employee-platform"
$Required=@(
 "src\main.py",
 "src\api\routes\request_compare.py",
 "src\api\routes\request_auto_compare.py",
 "src\api\routes\sales.py",
 "src\api\routes\deploy.py",
 "src\api\routes\system.py",
 "src\domain\deploy.py",
 "src\db\session.py",
 "src\db\models.py",
 "src\db\migrations.py"
)
foreach($r in $Required){
 if(!(Test-Path (Join-Path $App $r))){throw "Required file missing: $r"}
}
Push-Location $App
try{
 $env:PYTHONPATH=$App
 & $PythonExe -m compileall -q src
 if($LASTEXITCODE -ne 0){throw "compileall failed"}
 & $PythonExe -c "from src.domain.deploy import DeployRequest, DeployResult; from src.main import app; print('PREFLIGHT IMPORT OK')"
 if($LASTEXITCODE -ne 0){throw "preflight import failed"}
}finally{Pop-Location}
