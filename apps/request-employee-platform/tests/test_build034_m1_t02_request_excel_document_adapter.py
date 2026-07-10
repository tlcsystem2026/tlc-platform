from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

from src.services.request_excel_document_adapter import (
    parse_request_documents_xlsx,
    request_document_from_mapping,
)


def _minimal_xlsx() -> bytes:
    files = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Requests" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="inlineStr"><is><t>请求书编号</t></is></c>
      <c r="B1" t="inlineStr"><is><t>客户名称</t></is></c>
      <c r="C1" t="inlineStr"><is><t>合计</t></is></c>
      <c r="D1" t="inlineStr"><is><t>币种</t></is></c>
    </row>
    <row r="2">
      <c r="A2" t="inlineStr"><is><t>REQ-034-001</t></is></c>
      <c r="B2" t="inlineStr"><is><t>东京客户A</t></is></c>
      <c r="C2"><v>1234.50</v></c>
      <c r="D2" t="inlineStr"><is><t>JPY</t></is></c>
    </row>
  </sheetData>
</worksheet>""",
    }

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buffer.getvalue()


def test_request_document_from_mapping_multilang_aliases():
    document = request_document_from_mapping(
        {
            "請求書番号": "JP-001",
            "顧客名": "顧客A",
            "請求金額": "1,500",
            "通貨": "JPY",
        },
        source_name="sample.xlsx",
    )

    assert document.request_no == "JP-001"
    assert document.customer_name == "顧客A"
    assert document.total_amount == "1500"
    assert document.currency == "JPY"


def test_parse_request_documents_xlsx_without_openpyxl():
    documents = parse_request_documents_xlsx(
        _minimal_xlsx(),
        source_name="request_sample.xlsx",
    )

    assert len(documents) == 1
    document = documents[0]
    assert document.request_no == "REQ-034-001"
    assert document.customer_name == "东京客户A"
    assert document.total_amount == "1234.50"
    assert document.currency == "JPY"
    assert document.source_sheet == "Requests"
    assert document.source_row == 2
