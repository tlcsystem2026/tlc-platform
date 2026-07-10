from src.services.request_document_compare_adapter import (
    compare_request_documents,
    to_legacy_compare_payload,
)


def _excel(**overrides):
    data = {
        "source_name": "request.xlsx",
        "request_no": "REQ-001",
        "request_date": "2026/07/10",
        "customer_id": "C001",
        "customer_name": "Example Customer",
        "currency": "jpy",
        "subtotal": "1,000",
        "tax_amount": "100",
        "total_amount": "1,100",
    }
    data.update(overrides)
    return data


def _pdf(**overrides):
    data = {
        "source_name": "request.pdf",
        "request_no": "REQ-001",
        "request_date": "2026-07-10",
        "customer_id": "C001",
        "customer_name": " example   customer ",
        "currency": "JPY",
        "subtotal": "1000.0",
        "tax_amount": "100.00",
        "total_amount": "1100.000",
    }
    data.update(overrides)
    return data


def test_equivalent_excel_and_pdf_documents_match_after_normalization():
    result = compare_request_documents(_excel(), _pdf())

    assert result.matched is True
    assert result.differences == []
    assert result.request_no == "REQ-001"


def test_compare_reports_field_level_differences():
    result = compare_request_documents(
        _excel(total_amount="1100"),
        _pdf(total_amount="1200", customer_id="C999"),
    )

    assert result.matched is False
    assert [item.field for item in result.differences] == ["customer_id", "total_amount"]
    assert result.differences[-1].severity == "error"


def test_legacy_payload_is_stable_for_existing_api_and_persistence():
    result = compare_request_documents(
        _excel(),
        _pdf(total_amount="999"),
    )
    payload = to_legacy_compare_payload(result)

    assert payload["request_no"] == "REQ-001"
    assert payload["matched"] is False
    assert payload["difference_count"] == 1
    assert payload["differences"][0]["field"] == "total_amount"
    assert payload["differences"][0]["left"] == "1,100"
    assert payload["differences"][0]["right"] == "999"
    assert payload["sources"]["excel"] == "request.xlsx"
    assert payload["sources"]["pdf"] == "request.pdf"


def test_money_normalization_ignores_scale_only():
    result = compare_request_documents(
        _excel(subtotal="100", tax_amount="100.0", total_amount="100.00"),
        _pdf(subtotal="100.000", tax_amount="100", total_amount="100"),
    )
    assert result.matched is True
