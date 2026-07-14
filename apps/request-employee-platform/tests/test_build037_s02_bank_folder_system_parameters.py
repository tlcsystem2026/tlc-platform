
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_bank_folder_settings_save_check_and_account_creation(tmp_path, monkeypatch):
    monkeypatch.setenv("TLC_CONFIG_ROOT", str(tmp_path / "config"))
    root = tmp_path / "bank-data"
    payload = {
        "bank_root_path": str(root),
        "bank_incoming_dir": "Incoming",
        "bank_processing_dir": "Processing",
        "bank_completed_dir": "Completed",
        "bank_error_dir": "Error",
        "bank_archive_dir": "Archive",
    }
    saved = client.put("/api/tlc-system-parameters/bank-folders", json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json() == payload
    for name in ("Incoming", "Processing", "Completed", "Error", "Archive"):
        assert (root / name).is_dir()

    ensured = client.post(
        "/api/tlc-system-parameters/bank-folders/bank-accounts/yucho1/ensure"
    )
    assert ensured.status_code == 200, ensured.text
    for name in ("Incoming", "Processing", "Completed", "Error", "Archive"):
        assert (root / name / "yucho1").is_dir()

    (root / "Incoming" / "Yucho 2").mkdir(parents=True)
    checked = client.get("/api/tlc-system-parameters/bank-folders/check")
    assert checked.status_code == 200, checked.text
    body = checked.json()
    assert body["all_standard_directories_ready"] is True
    assert "yucho1" in body["bank_account_codes"]
    assert "incoming/Yucho 2" in body["invalid_bank_account_folders"]

def test_invalid_bank_account_code_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("TLC_CONFIG_ROOT", str(tmp_path / "config"))
    response = client.post(
        "/api/tlc-system-parameters/bank-folders/bank-accounts/Yucho%201/ensure"
    )
    assert response.status_code == 400

def test_system_parameter_page_contains_bank_section():
    response = client.get("/system-parameter-center")
    assert response.status_code == 200
    html = response.text
    assert "银行流水目录设置" in html
    assert "/api/tlc-system-parameters/bank-folders" in html
    assert "创建缺失目录" not in html
