from src.api.routes import customer_reconciliation as mod


def test_customer_reconciliation_page_contains_build033_pdf_binding():
    source = getattr(mod, "PAGE_HTML", "")
    assert "Build033R3 T002 UI PDF Integration" in source
    assert "/api/customer-reconciliation/cutoffs/export/pdf" in source
