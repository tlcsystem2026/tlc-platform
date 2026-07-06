from pathlib import Path
import subprocess
from fastapi import APIRouter, HTTPException
from src.domain.deploy import DeployRequest, DeployResult
router=APIRouter(prefix="/api/deploy",tags=["deploy"])
DOWNLOAD_ROOT=Path(r"Y:\TLC-BOS\Downloads")
REPO_ROOT=Path(r"Y:\TLC-BOS\Repository\projects\tlc-platform")
SCRIPT=REPO_ROOT/"scripts"/"tlc-controlled-deploy.ps1"
@router.post("/local",response_model=DeployResult)
def deploy_local(req: DeployRequest):
    package=DOWNLOAD_ROOT/req.package_name
    if package.parent != DOWNLOAD_ROOT or not package.exists():
        raise HTTPException(status_code=404,detail="ZIP package not found")
    if not SCRIPT.exists():
        raise HTTPException(status_code=500,detail="controlled deployment script missing")
    cmd=["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(SCRIPT),
         "-PackageName",req.package_name,"-RunTests",str(req.run_tests).lower(),
         "-StartApi",str(req.start_api).lower()]
    p=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",errors="replace")
    tail=((p.stdout or "")+"\n"+(p.stderr or ""))[-12000:]
    return DeployResult(status="success" if p.returncode==0 else "failed",
        package_name=req.package_name,return_code=p.returncode,output_tail=tail)
