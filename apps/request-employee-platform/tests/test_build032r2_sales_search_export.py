from io import BytesIO
from zipfile import ZipFile
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_sales_search_endpoint():
    r = client.get("/api/sales", params={"keyword": "", "status": ""})
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_sales_xlsx_export_is_real_zip_package():
    r = client.get("/api/sales/export/excel")
    assert r.status_code == 200
    assert "spreadsheetml.sheet" in r.headers["content-type"]
    with ZipFile(BytesIO(r.content)) as z:
        assert "xl/workbook.xml" in z.namelist()
        assert "xl/worksheets/sheet1.xml" in z.namelist()

def test_sales_pdf_export_has_valid_header():
    r = client.get("/api/sales/export/pdf")
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-1.4")
