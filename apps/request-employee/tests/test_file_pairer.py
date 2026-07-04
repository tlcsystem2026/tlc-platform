from pathlib import Path
from pairing.file_pairer import FilePairer

def test_pair_by_invoice(tmp_path: Path):
    pdf = tmp_path / "東京恋人請求書_税込_LY01006_1230_新川.pdf"
    xlsx = tmp_path / "東京恋人請求書_税込_LY01006_1230_新川.xlsx"
    pdf.write_text("x")
    xlsx.write_text("x")
    pairs = FilePairer().pair(tmp_path, tmp_path)
    assert pairs[0]["status"] == "PAIRED"
    assert pairs[0]["method"] == "invoice_no"
