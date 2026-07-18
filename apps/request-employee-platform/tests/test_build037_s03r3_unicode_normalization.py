from src.services import request_batch_compare_import_service as service


def test_s03r3_nfkc_normalizes_compatibility_ideographs():
    pdf_text = """
    登録番号： T9011401020619
    御請求⾦額 ¥405,000 円
    合計 150 ¥405,000 円
    """
    assert service._pdf_labeled_total(pdf_text) == "405000"
    assert service._pdf_labeled_total(pdf_text) != "9011401020619"
