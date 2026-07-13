
from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def finished_month(month: str):
    batch = client.post("/api/tlc-batches", json={
        "business_month": month,
        "title": f"Signoff {uuid4().hex[:8]}",
        "created_by": "tester",
    }).json()
    for status in [
        "IMPORTING","COMPARE","READY_REVIEW","REVIEWING",
        "LEDGER_POSTED","BANK_IMPORTED","RECONCILING","FINISHED",
    ]:
        response = client.post(
            f"/api/tlc-batches/{batch['id']}/transition",
            json={"new_status": status, "operator": "tester"},
        )
        assert response.status_code == 200, response.text
    return batch

def test_checklist_and_signoff():
    month = "2099-04"
    finished_month(month)
    initialized = client.post(
        f"/api/tlc-monthly-close/{month}/checklist/initialize",
        json={"operator": "tester"},
    )
    assert initialized.status_code == 200, initialized.text
    items = initialized.json()["checklist"]
    assert len(items) == 8

    blocked = client.put(
        f"/api/tlc-monthly-close/{month}/signoff",
        json={"status": "APPROVED", "operator": "manager"},
    )
    assert blocked.status_code == 400

    for item in items:
        updated = client.put(
            f"/api/tlc-monthly-close/checklist/items/{item['id']}",
            json={"status": "DONE", "operator": "tester"},
        )
        assert updated.status_code == 200

    approved = client.put(
        f"/api/tlc-monthly-close/{month}/signoff",
        json={"status": "APPROVED", "operator": "manager", "note": "Month closed"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

def test_control_view_and_page():
    month = "2099-05"
    finished_month(month)
    client.post(
        f"/api/tlc-monthly-close/{month}/checklist/initialize",
        json={"operator": "tester"},
    )
    view = client.get(f"/api/tlc-monthly-close/{month}/control-view")
    assert view.status_code == 200
    assert view.json()["checklist_initialized"] is True
    assert view.json()["signoff"]["status"] == "DRAFT"

    html = client.get("/monthly-close-center").text
    assert "/control-view" in html
    assert "/checklist/initialize" in html
    assert "/signoff" in html
    assert "月结检查清单与签核" in html
