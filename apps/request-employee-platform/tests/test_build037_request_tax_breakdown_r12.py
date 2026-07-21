from src.services.request_tax_breakdown_service import (
    compare_tax_breakdowns,
    extract_tax_breakdown_from_text,
)

LEGUANO_PYPDF_TEXT = """
ご 請 求 額 \\x00 ① ＋ ② \\x00 ¥300,000
① 通 常 税 率 商 品
小 計 \\x00 税 抜 \\x00 ¥0
消 費 税 10% ¥0
税 込 額 ① 0
② 軽 減 税 率 商 品
小 計 \\x00 税 抜 \\x00 \\ 277,778
消 費 税 8% \\ 22,222
税 込 額 ② ¥300,000
ご 請 求 額 \\x00 ① ＋ ② \\x00 ¥300,000
"""

LY01071_PYPDF_TEXT = """
ご 請 求 額 \\x00 ① ＋ ② \\x00 ¥650,400
① 通 常 税 率 商 品
小 計 \\x00 税 抜 \\x00 ¥2,182
消 費 税 10% ¥218
税 込 額 ① 2,400
② 軽 減 税 率 商 品
小 計 \\x00 税 抜 \\x00 \\ 600,000
消 費 税 8% \\ 48,000
税 込 額 ② ¥648,000
ご 請 求 額 \\x00 ① ＋ ② \\x00 ¥650,400
"""


def test_leguano_actual_pypdf_spacing():
    actual = extract_tax_breakdown_from_text(LEGUANO_PYPDF_TEXT)
    assert actual["taxable_amount_10"] == "0"
    assert actual["tax_amount_10"] == "0"
    assert actual["tax_inclusive_amount_10"] == "0"
    assert actual["taxable_amount_8"] == "277778"
    assert actual["tax_amount_8"] == "22222"
    assert actual["tax_inclusive_amount_8"] == "300000"


def test_ly01071_actual_pypdf_spacing():
    actual = extract_tax_breakdown_from_text(LY01071_PYPDF_TEXT)
    assert actual["taxable_amount_10"] == "2182"
    assert actual["tax_amount_10"] == "218"
    assert actual["tax_inclusive_amount_10"] == "2400"
    assert actual["taxable_amount_8"] == "600000"
    assert actual["tax_amount_8"] == "48000"
    assert actual["tax_inclusive_amount_8"] == "648000"
    assert actual["tax_inclusive_amount_8"] != "2"


def test_matching_values_have_no_tax_exception():
    pdf = extract_tax_breakdown_from_text(LY01071_PYPDF_TEXT)
    assert compare_tax_breakdowns(pdf, dict(pdf)) == ([], [])
