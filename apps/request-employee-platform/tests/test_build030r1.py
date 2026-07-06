from pathlib import Path
from fastapi.testclient import TestClient
from src.main import app
c=TestClient(app)
def test_health_runtime_pages():
    assert c.get("/health").status_code==200
    assert c.get("/api/system/runtime").json()["version"]=="0.30.2-clean-true-full"
    for p in ("/dashboard","/review","/sales","/docs","/api/db/status"): assert c.get(p).status_code==200
def test_dashboard_contract():
    d=c.get("/api/dashboard/summary").json()
    assert len(d["navigator"])>=5
def test_deploy_validation():
    r=c.post("/api/deploy/local",json={"package_name":"..\\\\evil.ps1","run_tests":True,"start_api":False})
    assert r.status_code==422
def test_sales_roundtrip():
    r=c.post("/api/sales/post",json={"request_no":"BUILD030R1-SALES-001","sales_date":"2026-07-06",
      "customer_name":"株式会社 テスト","subtotal":"1000","tax_amount":"100","total_amount":"1100"})
    assert r.status_code==200 and r.json()["status"] in {"created","exists"}
    assert c.get("/api/sales/summary").json()["count"]>=1
def test_parser_compare():
    root=Path(__file__).parent/"fixtures"
    r=c.post("/api/requests/compare-parser-json",json={
      "pdf_json_path":str(root/"request_pdf_parser_sample.json"),
      "excel_json_path":str(root/"request_excel_parser_sample.json")})
    assert r.status_code==200 and r.json()["status"]=="matched"
