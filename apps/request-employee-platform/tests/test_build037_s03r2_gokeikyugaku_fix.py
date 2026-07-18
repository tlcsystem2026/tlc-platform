from pathlib import Path

from openpyxl import Workbook

from src.services import request_batch_compare_import_service as service


PDF_TEXT = """
請 求 書 兼 納 品 書
買取書番号：TK-YSS-20260107-0014
登録番号： T9011401020619
会員番号： 02498
請求日： 2026 年 01 月 06 日
株式会社 索島 御中
東京恋人株式会社
御請求金額 ¥405,000 円
合計 150 ¥405,000 円
"""


def _make_excel(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet["B18"] = "ご請求額（①＋②）"
    sheet["D18"] = 405000
    sheet["G6"] = "T9011401020619"
    workbook.save(path)
    workbook.close()


def test_s03r2_pdf_uses_gokeikyugaku_not_corporate_number(tmp_path):
    excel = tmp_path / "sample.xlsx"
    _make_excel(excel)
    data = service._extract_excel(excel)

    assert service._pdf_labeled_total(PDF_TEXT) == "405000"
    assert service._excel_labeled_total(data) == "405000"
    assert service._pdf_labeled_total(PDF_TEXT) != "9011401020619"
