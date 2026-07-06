$ErrorActionPreference="Stop"
$Repo="Y:\TLC-BOS\Repository\projects\tlc-platform";$Zip="Y:\TLC-BOS\Downloads\TLC_BUILD029_full_recovery_request_platform_FULL.zip";$Temp="Y:\TLC-BOS\Downloads\_TEMP_FULL_RECOVERY";$App="$Repo\apps\request-employee-platform";$Venv="C:\TLC-BOS\venv\request-employee-platform";$Py="$Venv\Scripts\python.exe"
if(Test-Path $Temp){Remove-Item $Temp -Recurse -Force}; Expand-Archive $Zip $Temp -Force; Copy-Item "$Temp\*" $Repo -Recurse -Force; Remove-Item $Temp -Recurse -Force
if(!(Test-Path $Py)){New-Item -ItemType Directory -Force "C:\TLC-BOS\venv"|Out-Null; python -m venv $Venv}
& $Py -m pip install --upgrade pip; & $Py -m pip install -r "$App\requirements.txt"
cd $App; $env:PYTHONPATH=$App; & $Py -m pytest -q; if($LASTEXITCODE -ne 0){throw "Tests failed"}
& $Py -m uvicorn src.main:app --host 127.0.0.1 --port 8018 --reload --reload-dir "$App\src"
