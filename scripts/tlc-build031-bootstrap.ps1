$ErrorActionPreference="Stop"
$D="Y:\TLC-BOS\Downloads"
$Name="TLC_BUILD031_DASHBOARD_RECOVERY_FULL.zip"
$Zip=Join-Path $D $Name
$T=Join-Path $D "_TLC_BOOTSTRAP_031"
if(!(Test-Path $Zip)){throw "Package not found: $Zip"}
if(Test-Path $T){Remove-Item $T -Recurse -Force}
Expand-Archive $Zip $T -Force
$Driver=Join-Path $T "scripts\tlc-controlled-deploy.ps1"
if(!(Test-Path $Driver)){throw "Controlled deploy driver missing"}
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Driver -PackageName $Name -RunTests true -StartApi true
if($LASTEXITCODE -ne 0){throw "Deployment failed; rollback requested"}
Remove-Item $T -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "SUCCESS: http://127.0.0.1:8018/dashboard" -ForegroundColor Green
