from src.services.request_tax_breakdown_service import (
    compare_tax_breakdowns,
    extract_tax_breakdown_from_text,
)

SAMPLE = """
①通常税率商品
小計（税抜）
¥637
消費税 10%
¥63
税込額①
¥700
②軽減税率商品
小計（税抜）
¥92,593
消費税 8%
¥7,407
税込額②
¥100,000
"""

SPLIT = """
①通常税率商品
小計（税抜）
¥2,182
消費税 10%
¥218
税込額①
2,400
②軽減税率商品
小計（税抜）
\\ 600,000
消費税 8%
\\ 48,000
税込額②
¥648,000
"""

def test_exact_user_diagnostic_sample():
    result = extract_tax_breakdown_from_text(SAMPLE)
    assert result["taxable_amount_10"] == "637"
    assert result["tax_amount_10"] == "63"
    assert result["tax_inclusive_amount_10"] == "700"
    assert result["taxable_amount_8"] == "92593"
    assert result["tax_amount_8"] == "7407"
    assert result["tax_inclusive_amount_8"] == "100000"

def test_split_pdf_uses_real_amount_not_circled_marker():
    result = extract_tax_breakdown_from_text(SPLIT)
    assert result["taxable_amount_10"] == "2182"
    assert result["tax_amount_10"] == "218"
    assert result["tax_inclusive_amount_10"] == "2400"
    assert result["taxable_amount_8"] == "600000"
    assert result["tax_amount_8"] == "48000"
    assert result["tax_inclusive_amount_8"] == "648000"
    assert result["tax_inclusive_amount_8"] != "2"

def test_equal_breakdowns_have_no_exception():
    pdf = extract_tax_breakdown_from_text(SPLIT)
    assert compare_tax_breakdowns(pdf, dict(pdf)) == ([], [])
