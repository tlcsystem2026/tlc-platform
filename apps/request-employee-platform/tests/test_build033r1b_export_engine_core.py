import pytest
from src.platform_config import get_config
from src.services.export_engine import ExportColumn, FontManager, build_export_model, export_csv_model, export_pdf_model, selfcheck_export_content

@pytest.fixture()
def config_root(tmp_path, monkeypatch):
    c=tmp_path/"config"; c.mkdir()
    (c/"app.yaml").write_text("app:\n  name: TLC\n  environment: test\n",encoding="utf-8")
    (c/"environment.yaml").write_text("environment:\n  current: test\n",encoding="utf-8")
    (c/"paths.yaml").write_text("paths:\n  repository_root: Y:/repo\n  export_root: Y:/export\n  temp_root: Y:/temp\n",encoding="utf-8")
    (c/"database.yaml").write_text("database:\n  default:\n    engine: sqlite\n",encoding="utf-8")
    (c/"logging.yaml").write_text("logging:\n  level: INFO\n",encoding="utf-8")
    (c/"export.yaml").write_text("export:\n  pdf:\n    engine: reportlab\n    fonts:\n      zh: STSong-Light\n      ja: HeiseiKakuGo-W5\n      en: Helvetica\n  csv:\n    encoding: utf-8-sig\n",encoding="utf-8")
    monkeypatch.setenv("TLC_CONFIG_ROOT",str(c)); get_config(c,reload=True); return c

def model():
    return build_export_model(title="客户对账清款 Export Engine", language="zh", filename="build033r1b_export_engine", columns=[ExportColumn("customer_id","客户ID"),ExportColumn("customer_name","客户名称"),ExportColumn("amount","金额",numeric=True)], rows=[{"customer_id":"C-001","customer_name":"東京顧客 Alpha","amount":"100"},{"customer_id":"C-002","customer_name":"中文客户 Beta","amount":"200"}])

def test_export_model_total(config_root):
    rows=model().export_rows()
    assert rows[0]["客户ID"]=="C-001"
    assert rows[-1]["客户ID"]=="合计"
    assert rows[-1]["金额"]=="300"

def test_font_manager_uses_config(config_root):
    assert FontManager.font_for("ABC","en")=="Helvetica"
    assert FontManager.font_for("中文","en")=="STSong-Light"
    assert FontManager.font_for("東京かな","en")=="HeiseiKakuGo-W5"

def test_csv_engine(config_root):
    text=export_csv_model(model()).body.decode("utf-8-sig")
    assert "客户ID" in text and "C-001" in text and "合计" in text

def test_pdf_engine(config_root):
    response=export_pdf_model(model())
    assert response.body.startswith(b"%PDF") and b"ReportLab" in response.body
    selfcheck_export_content(response.body,["客户对账清款 Export Engine","客户ID","合计","C-001"])
