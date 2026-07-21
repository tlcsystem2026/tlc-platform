from src.services import request_batch_compare_import_service as service


def test_pdf_recipient_regex_uses_whitespace_tokens_not_literal_backslashes():
    text = """
請 求 書
Y·Ｇ·Ｆ合同会社 御中
東京恋人株式会社
"""
    assert service._pdf_recipient_name(text) == "Y·G·F合同会社"


def test_recipient_on_previous_line_is_supported():
    text = """
請 求 書
株式会社ＭＹＵ企画
御中
東京恋人株式会社
"""
    assert service._pdf_recipient_name(text) == "株式会社MYU企画"
