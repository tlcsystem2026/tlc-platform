import sys
import types

from src.services.request_pdf_document_adapter import (
    parse_request_document_pdf,
    request_document_from_pdf_text,
)


def test_request_document_from_pdf_text_multilang_fields():
    text = """
請求書番号: REQ-PDF-034-001
請求日: 2026-07-10
顧客ID: CUST-900
顧客名: 東京顧客株式会社
通貨: JPY
小計: 1,000
消費税: 100
合計: 1,100
"""
    document = request_document_from_pdf_text(text, source_name="sample.pdf", page_no=1)

    assert document.request_no == "REQ-PDF-034-001"
    assert document.request_date == "2026-07-10"
    assert document.customer_id == "CUST-900"
    assert document.customer_name == "東京顧客株式会社"
    assert document.currency == "JPY"
    assert document.subtotal == "1000"
    assert document.tax_amount == "100"
    assert document.total_amount == "1100"


def test_parse_request_document_pdf_uses_pypdf_contract(monkeypatch):
    class FakePage:
        def extract_text(self):
            return "Request No: EN-001\\nCustomer Name: Example Customer\\nCurrency: USD\\nTotal Amount: 2500"

    class FakeReader:
        def __init__(self, content):
            assert content.startswith(b"%PDF")
            self.pages = [FakePage()]

    monkeypatch.setitem(sys.modules, "pypdf", types.SimpleNamespace(PdfReader=FakeReader))

    document = parse_request_document_pdf(b"%PDF-1.4 fake", source_name="english.pdf")

    assert document.request_no == "EN-001"
    assert document.customer_name == "Example Customer"
    assert document.currency == "USD"
    assert document.total_amount == "2500"


def test_customer_name_stops_at_next_real_line():
    document = request_document_from_pdf_text(
        "Customer Name: Example Customer\nCurrency: USD\nTotal Amount: 2500"
    )
    assert document.customer_name == "Example Customer"


def test_image_only_pdf_routes_to_future_ocr(monkeypatch):
    class FakePage:
        def extract_text(self):
            return ""

    class FakeReader:
        def __init__(self, content):
            self.pages = [FakePage()]

    monkeypatch.setitem(sys.modules, "pypdf", types.SimpleNamespace(PdfReader=FakeReader))

    try:
        parse_request_document_pdf(b"%PDF-1.4 image-only")
    except ValueError as exc:
        assert "image/OCR flow is required" in str(exc)
    else:
        raise AssertionError("Expected image-only PDF error")
