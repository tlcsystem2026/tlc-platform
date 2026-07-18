from src.services import request_batch_compare_import_service as service


def test_s03r4_skips_formula_digits_before_currency_amount():
    pdf_text = """
    ご請求額（①＋②） ¥650,400
    税込額① 2,400
    税込額② ¥648,000
    ご請求額（①＋②） ¥650,400
    """
    assert service._pdf_labeled_total(pdf_text) == "650400"


def test_s03r4_keeps_unicode_normalized_gokeikyugaku_amount():
    pdf_text = """
    登録番号： T9011401020619
    御請求⾦額 ¥405,000 円
    合計 150 ¥405,000 円
    """
    assert service._pdf_labeled_total(pdf_text) == "405000"
    assert service._pdf_labeled_total(pdf_text) != "9011401020619"
