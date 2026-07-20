from src.services.request_tax_breakdown_service import (
    compare_tax_breakdowns,
    extract_tax_breakdown_from_excel,
    extract_tax_breakdown_from_text,
)


PDF_TEXT = r"""
ご請求額（①＋②） ¥83,200
①通常税率商品
小計（税抜） ¥75,637
消費税 10% ¥7,563
税込額① 83,200
②軽減税率商品
小計（税抜） \ -
消費税 8% \ -
税込額② ¥0
ご請求額（①＋②） ¥83,200
"""


EXCEL_DATA = {
    "sheets": [
        {
            "title": "Sheet1",
            "rows": [
                [None, "ご請求額（①＋②）", None, 83200],
                [None, "①通常税率商品"],
                [None, "小計（税抜）", None, 75637],
                [None, "消費税", 0.1, 7563],
                [None, "税込額①", None, 83200],
                [None, "②軽減税率商品"],
                [None, "小計（税抜）", None, 0],
                [None, "消費税", 0.08, 0],
                [None, "税込額②", None, 0],
            ],
        }
    ]
}


def test_zero_reduced_tax_section_is_not_missing():
    pdf = extract_tax_breakdown_from_text(PDF_TEXT)
    excel = extract_tax_breakdown_from_excel(EXCEL_DATA)

    assert pdf["taxable_amount_8"] == "0"
    assert pdf["tax_amount_8"] == "0"
    assert pdf["tax_inclusive_amount_8"] == "0"

    assert excel["taxable_amount_8"] == "0"
    assert excel["tax_amount_8"] == "0"
    assert excel["tax_inclusive_amount_8"] == "0"

    codes, details = compare_tax_breakdowns(pdf, excel)
    assert "TAX_BREAKDOWN_MISSING" not in codes
    assert "TAX_AMOUNT_8_MISMATCH" not in codes
    assert codes == []
    assert details == []
