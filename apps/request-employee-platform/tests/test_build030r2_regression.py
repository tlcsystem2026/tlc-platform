import pytest
from pydantic import ValidationError
from src.domain.deploy import DeployRequest, DeployResult

def test_deploy_domain_module_imports():
    req = DeployRequest(package_name="TLC_TEST_FULL.zip", run_tests=True, start_api=False)
    assert req.package_name == "TLC_TEST_FULL.zip"
    result = DeployResult(status="success", package_name=req.package_name, return_code=0, output_tail="ok")
    assert result.return_code == 0

@pytest.mark.parametrize("bad", ["..\\evil.ps1", "../evil.zip", "folder/file.zip", "evil.ps1", ""])
def test_deploy_package_name_rejects_paths_and_non_zip(bad):
    with pytest.raises(ValidationError):
        DeployRequest(package_name=bad)
