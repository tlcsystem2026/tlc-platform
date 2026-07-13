
from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def finished_month(month):
    batch = client.post("/api/tlc-batches", json={
        "business_month": month,
        "title": f"Auth {uuid4().hex[:8]}",
        "created_by": "tester",
    }).json()
    for status in [
        "IMPORTING","COMPARE","READY_REVIEW","REVIEWING",
        "LEDGER_POSTED","BANK_IMPORTED","RECONCILING","FINISHED",
    ]:
        r = client.post(
            f"/api/tlc-batches/{batch['id']}/transition",
            json={"new_status": status, "operator": "tester"},
        )
        assert r.status_code == 200, r.text
    init = client.post(
        f"/api/tlc-monthly-close/{month}/checklist/initialize",
        json={"operator": "tester"},
    ).json()
    for item in init["checklist"]:
        r = client.put(
            f"/api/tlc-monthly-close/checklist/items/{item['id']}",
            json={"status": "DONE", "operator": "tester"},
        )
        assert r.status_code == 200
    approved = client.put(
        f"/api/tlc-monthly-close/{month}/signoff",
        json={"status": "APPROVED", "operator": "manager"},
    )
    assert approved.status_code == 200, approved.text
    return batch

def test_close_authorization_requires_separation_of_duties():
    month = "2099-12"
    finished_month(month)
    req = client.post("/api/tlc-monthly-close/authorizations", json={
        "business_month": month,
        "action": "CLOSE",
        "requested_by": "requester",
        "reason": "Ready to close",
    })
    assert req.status_code == 200, req.text
    auth = req.json()["authorization"]

    same = client.put(
        f"/api/tlc-monthly-close/authorizations/{auth['id']}/decision",
        json={"decision": "APPROVED", "approver": "requester"},
    )
    assert same.status_code == 400
    assert "must be different" in same.json()["detail"]

    approved = client.put(
        f"/api/tlc-monthly-close/authorizations/{auth['id']}/decision",
        json={"decision": "APPROVED", "approver": "manager"},
    )
    assert approved.status_code == 200
    assert approved.json()["decision"] == "APPROVED"

    executed = client.put(
        f"/api/tlc-monthly-close/authorizations/{auth['id']}/execute",
        json={"operator": "operator"},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["decision"] == "EXECUTED"

def test_reopen_changes_signoff_and_audit_is_recorded():
    month = "2100-01"
    finished_month(month)
    req = client.post("/api/tlc-monthly-close/authorizations", json={
        "business_month": month,
        "action": "REOPEN",
        "requested_by": "requester",
    }).json()["authorization"]
    client.put(
        f"/api/tlc-monthly-close/authorizations/{req['id']}/decision",
        json={"decision": "APPROVED", "approver": "manager"},
    )
    executed = client.put(
        f"/api/tlc-monthly-close/authorizations/{req['id']}/execute",
        json={"operator": "operator", "note": "Need correction"},
    )
    assert executed.status_code == 200, executed.text

    view = client.get(
        f"/api/tlc-monthly-close/{month}/control-view"
    )
    assert view.status_code == 200
    assert view.json()["signoff"]["status"] == "REOPENED"

    audit = client.get(
        "/api/tlc-monthly-close/authorizations/audit",
        params={"business_month": month},
    )
    assert audit.status_code == 200
    assert len(audit.json()) >= 3
    assert any(x["event_type"] == "AUTHORIZATION_EXECUTED" for x in audit.json())

def test_page_connected():
    html = client.get("/monthly-close-center").text
    assert "/api/tlc-monthly-close/authorizations" in html
    assert "关闭 / 重开授权与审计" in html
    assert "Audit Trail" in html
