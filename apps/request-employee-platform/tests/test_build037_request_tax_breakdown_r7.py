from src.services.request_tax_breakdown_service import (
    compare_tax_breakdowns,
    extract_tax_breakdown_from_text,
)

SPLIT_PDF = r"""
①通常税率商品
小計（税抜）
¥2,182
消費税 10%
¥218
税込額①
2,400
②軽減税率商品
小計（税抜）
\ 600,000
消費税 8%
\ 48,000
税込額②
¥648,000
"""

def test_split_pdf_lines_do_not_use_section_marker_as_amount():
    actual = extract_tax_breakdown_from_text(SPLIT_PDF)
    assert actual["taxable_amount_10"] == "2182"
    assert actual["tax_amount_10"] == "218"
    assert actual["tax_inclusive_amount_10"] == "2400"
    assert actual["taxable_amount_8"] == "600000"
    assert actual["tax_amount_8"] == "48000"
    assert actual["tax_inclusive_amount_8"] == "648000"

def test_pdf_value_two_is_not_taken_from_circled_two():
    actual = extract_tax_breakdown_from_text(
        "②軽減税率商品\n税込額②\n¥300,000"
    )
    assert actual["tax_inclusive_amount_8"] == "300000"
    assert actual["tax_inclusive_amount_8"] != "2"

def test_complete_breakdown_no_longer_reports_missing():
    pdf = extract_tax_breakdown_from_text(SPLIT_PDF)
    excel = {
        "taxable_amount_10": "2182",
        "tax_amount_10": "218",
        "tax_inclusive_amount_10": "2400",
        "taxable_amount_8": "600000",
        "tax_amount_8": "48000",
        "tax_inclusive_amount_8": "648000",
        "non_taxable_amount": "",
        "tax_exempt_amount": "",
        "subtotal": "602182",
        "tax_amount": "48218",
        "total_amount": "650400",
    }
    codes, details = compare_tax_breakdowns(pdf, excel)
    assert codes == []
    assert details == []
