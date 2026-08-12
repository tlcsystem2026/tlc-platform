from fastapi.testclient import TestClient

from src.api.routes import multi_bank_import
from src.main import app


client = TestClient(app)


def test_bank_import_page_requires_bank_selection_before_file():
    response = client.get("/bank-import")
    assert response.status_code == 200
    html = response.text
    assert 'id="importBankCode"' in html
    assert 'id="bankFile" type="file" accept=".csv,text/csv" disabled' in html
    assert 'onchange="handleImportBankChange()"' in html
    assert "selected_bank_code" in html
    assert "与所选银行不一致时整批拒绝" in html


def test_selected_bank_is_required():
    response = client.post(
        "/api/bank-import/csv?source_name=test.csv",
        content=b"test",
        headers={"content-type": "text/csv"},
    )
    assert response.status_code == 422


def test_mismatched_bank_is_rejected_before_parse_and_import(monkeypatch):
    called = {"parse": False, "import": False}
    monkeypatch.setattr(
        multi_bank_import,
        "detect_bank_csv",
        lambda _content: "JAPAN_POST_BANK",
    )

    def fail_parse(*_args, **_kwargs):
        called["parse"] = True
        raise AssertionError("parse must not run for a mismatched bank")

    def fail_import(*_args, **_kwargs):
        called["import"] = True
        raise AssertionError("import must not run for a mismatched bank")

    monkeypatch.setattr(multi_bank_import, "parse_bank_csv", fail_parse)
    monkeypatch.setattr(multi_bank_import, "import_bank_transactions", fail_import)
    response = client.post(
        "/api/bank-import/csv",
        params={
            "source_name": "wrong.csv",
            "selected_bank_code": "SUGAMO_SHINKIN",
        },
        content=b"csv-content",
        headers={"content-type": "text/csv"},
    )
    assert response.status_code == 400
    assert "selected=SUGAMO_SHINKIN" in response.json()["detail"]
    assert "detected=JAPAN_POST_BANK" in response.json()["detail"]
    assert called == {"parse": False, "import": False}
