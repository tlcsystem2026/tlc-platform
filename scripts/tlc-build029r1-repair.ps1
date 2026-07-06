$ErrorActionPreference="Stop"
$Repo="Y:\TLC-BOS\Repository\projects\tlc-platform"
$Zip="Y:\TLC-BOS\Downloads\TLC_BUILD029R1_full_recovery_corrected_FULL.zip"
$Temp="Y:\TLC-BOS\Downloads\_TEMP_BUILD029R1"
$App="$Repo\apps\request-employee-platform"
$Py="C:\TLC-BOS\venv\request-employee-platform\Scripts\python.exe"
if(Test-Path $Temp){Remove-Item $Temp -Recurse -Force}
Expand-Archive $Zip $Temp -Force
Copy-Item "$Temp\*" $Repo -Recurse -Force
Remove-Item $Temp -Recurse -Force
cd $App
$env:PYTHONPATH=$App
$env:TLC_DATABASE_URL="sqlite:///C:/TLC-BOS/data/test/request_platform_test.db"
& $Py -m pytest -q
if($LASTEXITCODE -ne 0){throw "Build029R1 tests failed."}
& $Py -m uvicorn src.main:app --host 127.0.0.1 --port 8018
