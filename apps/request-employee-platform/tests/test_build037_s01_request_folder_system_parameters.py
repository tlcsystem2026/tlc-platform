from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_request_folder_settings_save_check_and_month_creation(tmp_path, monkeypatch):
    monkeypatch.setenv("TLC_CONFIG_ROOT", str(tmp_path / "config"))
    root = tmp_path / "request-data"
    payload = {
        "request_root_path": str(root),
        "request_incoming_dir": "Incoming",
        "request_processing_dir": "Processing",
        "request_completed_dir": "Completed",
        "request_error_dir": "Error",
        "request_archive_dir": "Archive",
        "request_month_folder_format": "YYYYMM",
    }
    saved = client.put("/api/tlc-system-parameters/request-folders", json=payload)
    assert saved.status_code == 200, saved.text
    for name in ("Incoming", "Processing", "Completed", "Error", "Archive"):
        assert (root / name).is_dir()
    ensured = client.post("/api/tlc-system-parameters/request-folders/months/202601/ensure")
    assert ensured.status_code == 200, ensured.text
    for name in ("Incoming", "Processing", "Completed", "Error", "Archive"):
        assert (root / name / "202601").is_dir()
    (root / "Incoming" / "202613").mkdir(parents=True)
    checked = client.get("/api/tlc-system-parameters/request-folders/check")
    assert checked.status_code == 200
    body = checked.json()
    assert "202601" in body["valid_month_folders"]
    assert "202613" in body["invalid_month_folders"]


def test_invalid_month_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("TLC_CONFIG_ROOT", str(tmp_path / "config"))
    response = client.post("/api/tlc-system-parameters/request-folders/months/202613/ensure")
    assert response.status_code == 400


def test_system_parameter_page():
    response = client.get("/system-parameter-center")
    assert response.status_code == 200
    assert "请求书导入目录设置" in response.text
    assert "创建缺失目录" not in response.text
