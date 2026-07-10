from src.api.routes import customer_reconciliation as mod

def test_customer_reconciliation_page_contains_build033_excel_binding():
    source = getattr(mod, "PAGE_HTML", "")
    assert "Build033R3 T001 UI Excel Integration" in source
    assert "/api/customer-reconciliation/cutoffs/export/excel" in source
