from src.services.request_tax_breakdown_service import (
    compare_tax_breakdowns,
    extract_tax_breakdown_from_excel,
    extract_tax_breakdown_from_text,
)


PDF_TEXT = """
ご請求額（①＋②） ¥1,785,700
①通常税率商品
小計（税抜） ¥637
消費税 10% ¥63
税込額① 700
②軽減税率商品
小計（税抜） \\ 1,652,778
消費税 8% \\ 132,222
税込額② ¥1,785,000
ご請求額（①＋②） ¥1,785,700
"""


EXCEL_DATA = {
    "sheets": [
        {
            "title": "Sheet1",
            "rows": [
                [None, "ご請求額（①＋②）", None, 1785700],
                [None, "①通常税率商品"],
                [None, "【備考】", None, None, None, None,
                 "小計（税抜）", None, 637],
                [None, None, None, None, None, None,
                 "消費税", 0.1, 63],
                [None, None, None, None, None, None,
                 "税込額①", None, 700],
                [None, "②軽減税率商品"],
                [None, "【備考】", None, None, None, None,
                 "小計（税抜）", None, 1652778],
                [None, None, None, None, None, None,
                 "消費税", 0.08, 132222],
                [None, None, None, None, None, None,
                 "税込額②", None, 1785000],
            ],
        }
    ]
}


def expected():
    return {
        "taxable_amount_10": "637",
        "tax_amount_10": "63",
        "tax_inclusive_amount_10": "700",
        "taxable_amount_8": "1652778",
        "tax_amount_8": "132222",
        "tax_inclusive_amount_8": "1785000",
    }


def test_pdf_section_context_extracts_both_tax_rates():
    actual = extract_tax_breakdown_from_text(PDF_TEXT)
    for key, value in expected().items():
        assert actual[key] == value


def test_excel_section_context_extracts_both_tax_rates():
    actual = extract_tax_breakdown_from_excel(EXCEL_DATA)
    for key, value in expected().items():
        assert actual[key] == value


def test_matching_tax_sections_do_not_raise_missing():
    pdf = extract_tax_breakdown_from_text(PDF_TEXT)
    excel = extract_tax_breakdown_from_excel(EXCEL_DATA)
    codes, details = compare_tax_breakdowns(pdf, excel)
    assert "TAX_BREAKDOWN_MISSING" not in codes
    assert codes == []
    assert details == []
