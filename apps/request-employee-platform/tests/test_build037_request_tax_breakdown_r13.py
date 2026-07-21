from src.services.request_tax_breakdown_service import (
    compare_tax_breakdowns,
    extract_tax_breakdown_from_text,
)


LY01163 = r"""
①通常税率商品
小計（税抜） ¥0
消費税 10% ¥0
税込額① 0
②軽減税率商品
小計（税抜） \ 49,500
消費税 8% \ 3,96
税込額② ¥53,460
"""

LY01186 = r"""
①通常税率商品
小計（税抜） ¥0
消費税 10% ¥0
税込額① 0
②軽減税率商品
小計（税抜） \ 8,22
消費税 8% \ 65
税込額② ¥8,883
"""

LY01187 = r"""
①通常税率商品
小計（税抜） ¥819
消費税 10% ¥81
税込額① 900
②軽減税率商品
小計（税抜） \ 20,00
消費税 8% \ 1,6
税込額② ¥21,600
"""

LY01188 = r"""
①通常税率商品
小計（税抜） ¥637
消費税 10% ¥63
税込額① 700
②軽減税率商品
小計（税抜） \ 62,96
消費税 8% \ 5,0
税込額② ¥68,000
"""

ZERO_8 = r"""
①通常税率商品
小計（税抜） ¥12,797
消費税 10% ¥1,279
税込額① 14,076
②軽減税率商品
小計（税抜） \ -
消費税 8% \ -
税込額② ¥0
"""


def test_ly01163_repairs_truncated_tax():
    actual = extract_tax_breakdown_from_text(LY01163)
    assert actual["taxable_amount_8"] == "49500"
    assert actual["tax_amount_8"] == "3960"
    assert actual["tax_inclusive_amount_8"] == "53460"


def test_ly01186_repairs_both_truncated_values():
    actual = extract_tax_breakdown_from_text(LY01186)
    assert actual["taxable_amount_8"] == "8225"
    assert actual["tax_amount_8"] == "658"
    assert actual["tax_inclusive_amount_8"] == "8883"


def test_ly01187_repairs_truncated_values():
    actual = extract_tax_breakdown_from_text(LY01187)
    assert actual["taxable_amount_8"] == "20000"
    assert actual["tax_amount_8"] == "1600"
    assert actual["tax_inclusive_amount_8"] == "21600"


def test_ly01188_repairs_truncated_values():
    actual = extract_tax_breakdown_from_text(LY01188)
    assert actual["taxable_amount_8"] == "62963"
    assert actual["tax_amount_8"] == "5037"
    assert actual["tax_inclusive_amount_8"] == "68000"


def test_zero_rate_section_is_all_zero_not_eight_yen():
    actual = extract_tax_breakdown_from_text(ZERO_8)
    assert actual["taxable_amount_8"] == "0"
    assert actual["tax_amount_8"] == "0"
    assert actual["tax_inclusive_amount_8"] == "0"


def test_matching_excel_has_no_exception():
    pdf = extract_tax_breakdown_from_text(LY01188)
    excel = dict(pdf)
    assert compare_tax_breakdowns(pdf, excel) == ([], [])
