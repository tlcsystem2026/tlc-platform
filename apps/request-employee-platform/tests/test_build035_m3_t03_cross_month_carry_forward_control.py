
from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app

client=TestClient(app)

def make_batch(month):
    r=client.post("/api/tlc-batches",json={"business_month":month,"title":f"Carry {uuid4().hex[:8]}","created_by":"tester"})
    assert r.status_code==200,r.text
    return r.json()

def test_manual_create_update_view():
    source,target="2099-07","2099-08";b=make_batch(source)
    created=client.post("/api/tlc-monthly-close/carry-forwards",json={
      "source_month":source,"target_month":target,"source_batch_id":b["id"],
      "category":"UNPAID","reference_id":f"REF-{uuid4().hex}",
      "title":"Outstanding customer balance","amount":"1000","currency":"JPY","created_by":"tester"})
    assert created.status_code==200,created.text
    item=created.json()["carry_forward"];assert item["status"]=="OPEN"
    updated=client.put(f"/api/tlc-monthly-close/carry-forwards/{item['id']}",json={
      "status":"CONFIRMED","operator":"tester","resolution_note":"Carry to next month"})
    assert updated.status_code==200 and updated.json()["status"]=="CONFIRMED"
    view=client.get(f"/api/tlc-monthly-close/carry-forwards/control-view/{target}")
    assert view.status_code==200 and view.json()["incoming_open_count"]==1

def test_auto_generate_idempotent():
    source,target="2099-09","2099-10";make_batch(source)
    payload={"source_month":source,"target_month":target,"operator":"tester"}
    first=client.post("/api/tlc-monthly-close/carry-forwards/auto-generate",json=payload)
    second=client.post("/api/tlc-monthly-close/carry-forwards/auto-generate",json=payload)
    assert first.status_code==200 and second.status_code==200
    assert first.json()["created_count"]>=1
    assert second.json()["created_count"]==0
    assert second.json()["existing_count"]>=1

def test_invalid_month_order():
    r=client.post("/api/tlc-monthly-close/carry-forwards",json={
      "source_month":"2099-11","target_month":"2099-10","category":"TEST",
      "reference_id":f"REF-{uuid4().hex}","title":"Invalid","created_by":"tester"})
    assert r.status_code==400
    assert "target_month must be after source_month" in r.json()["detail"]

def test_page_connected():
    html=client.get("/monthly-close-center").text
    assert "/api/tlc-monthly-close/carry-forwards" in html
    assert "跨月结转控制" in html
    assert "从阻塞事项生成结转" in html
