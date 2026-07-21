from src.services import request_batch_compare_import_service as service

YGF_PDF = """
請 求 書
請求日 2026年1月14日
請求書番号 LY01106
Y·Ｇ·Ｆ合同会社 御中
東京恋人株式会社
"""

MYU_PDF = """
請 求 書
請求日 2026年1月5日
請求書番号 LY01021
株式会社ＭＹＵ企画 御中
東京恋人株式会社
"""

def test_middle_dot_variants_match():
    assert service._customer_name_found_in_pdf("Y・G・F合同会社", YGF_PDF)

def test_fullwidth_latin_variants_match():
    assert service._customer_name_found_in_pdf("株式会社MYU企画", MYU_PDF)

def test_issuer_is_not_recipient():
    assert service._pdf_recipient_name(YGF_PDF) == "Y·G·F合同会社"
    assert not service._customer_name_found_in_pdf("東京恋人株式会社", YGF_PDF)
