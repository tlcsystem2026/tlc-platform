from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile


HEADER_ALIASES = {
    "request_no": {
        "request no", "request_no", "request number", "invoice no", "invoice number",
        "请求书编号", "請求書番号", "請求番号", "单号", "伝票番号",
    },
    "request_date": {
        "request date", "request_date", "invoice date", "请求日期", "請求日", "発行日",
    },
    "customer_id": {
        "customer id", "customer_id", "client id", "客户id", "顧客id", "得意先コード",
    },
    "customer_name": {
        "customer name", "customer_name", "client name", "客户名称", "顧客名", "得意先名",
    },
    "currency": {
        "currency", "币种", "通貨",
    },
    "subtotal": {
        "subtotal", "sub total", "税前金额", "小计", "小計", "税抜金額",
    },
    "tax_amount": {
        "tax", "tax amount", "tax_amount", "税额", "消費税",
    },
    "total_amount": {
        "total", "total amount", "total_amount", "合计", "合計", "請求金額", "税込金額",
    },
}


def _normalize_header(value: Any) -> str:
    return str(value or "").strip().lower().replace("\n", " ")


def _header_key(value: Any) -> str | None:
    normalized = _normalize_header(value)
    for key, aliases in HEADER_ALIASES.items():
        if normalized in aliases:
            return key
    return None


def _decimal_text(value: Any) -> str:
    raw = str(value or "").strip().replace(",", "").replace("¥", "").replace("$", "")
    if raw == "":
        return ""
    try:
        return format(Decimal(raw), "f")
    except InvalidOperation:
        return raw


@dataclass(slots=True)
class RequestDocument:
    source_type: str
    source_name: str
    request_no: str = ""
    request_date: str = ""
    customer_id: str = ""
    customer_name: str = ""
    currency: str = ""
    subtotal: str = ""
    tax_amount: str = ""
    total_amount: str = ""
    source_sheet: str = ""
    source_row: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_name": self.source_name,
            "request_no": self.request_no,
            "request_date": self.request_date,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "currency": self.currency,
            "subtotal": self.subtotal,
            "tax_amount": self.tax_amount,
            "total_amount": self.total_amount,
            "source_sheet": self.source_sheet,
            "source_row": self.source_row,
            "raw": self.raw,
        }


def request_document_from_mapping(
    row: dict[str, Any],
    *,
    source_name: str,
    source_sheet: str = "",
    source_row: int = 0,
) -> RequestDocument:
    normalized: dict[str, Any] = {}
    for header, value in row.items():
        key = _header_key(header)
        if key:
            normalized[key] = value

    return RequestDocument(
        source_type="excel",
        source_name=source_name,
        request_no=str(normalized.get("request_no", "") or "").strip(),
        request_date=str(normalized.get("request_date", "") or "").strip(),
        customer_id=str(normalized.get("customer_id", "") or "").strip(),
        customer_name=str(normalized.get("customer_name", "") or "").strip(),
        currency=str(normalized.get("currency", "") or "").strip(),
        subtotal=_decimal_text(normalized.get("subtotal", "")),
        tax_amount=_decimal_text(normalized.get("tax_amount", "")),
        total_amount=_decimal_text(normalized.get("total_amount", "")),
        source_sheet=source_sheet,
        source_row=source_row,
        raw={str(k): v for k, v in row.items()},
    )


def _shared_strings(zf: ZipFile) -> list[str]:
    try:
        xml = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []

    root = ET.fromstring(xml)
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    values: list[str] = []
    for si in root.findall("a:si", ns):
        texts = [node.text or "" for node in si.findall(".//a:t", ns)]
        values.append("".join(texts))
    return values


def _sheet_rows(zf: ZipFile, sheet_path: str, shared: list[str]) -> list[list[Any]]:
    xml = zf.read(sheet_path)
    root = ET.fromstring(xml)
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

    rows: list[list[Any]] = []
    for row in root.findall(".//a:sheetData/a:row", ns):
        cells: list[Any] = []
        last_col = 0
        for cell in row.findall("a:c", ns):
            ref = cell.attrib.get("r", "A1")
            letters = "".join(ch for ch in ref if ch.isalpha())
            col = 0
            for ch in letters:
                col = col * 26 + (ord(ch.upper()) - 64)

            while last_col + 1 < col:
                cells.append("")
                last_col += 1

            cell_type = cell.attrib.get("t")
            value_node = cell.find("a:v", ns)
            inline_node = cell.find("a:is/a:t", ns)

            value: Any = ""
            if inline_node is not None:
                value = inline_node.text or ""
            elif value_node is not None:
                raw = value_node.text or ""
                if cell_type == "s" and raw.isdigit():
                    idx = int(raw)
                    value = shared[idx] if idx < len(shared) else raw
                else:
                    value = raw

            cells.append(value)
            last_col = col

        rows.append(cells)
    return rows


def parse_request_documents_xlsx(
    content: bytes,
    *,
    source_name: str = "request.xlsx",
) -> list[RequestDocument]:
    """Parse a simple tabular XLSX into standard RequestDocument records.

    The first row containing two or more recognized headers is treated as the
    header row. Each following non-empty row becomes one RequestDocument.
    This adapter intentionally uses only the Python standard library.
    """
    with ZipFile(BytesIO(content)) as zf:
        shared = _shared_strings(zf)
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))

        ns_main = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        ns_rel = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}

        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall("r:Relationship", ns_rel)
        }

        results: list[RequestDocument] = []
        for sheet in workbook.findall("a:sheets/a:sheet", ns_main):
            sheet_name = sheet.attrib.get("name", "")
            rel_id = sheet.attrib.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            target = rel_map.get(rel_id or "", "")
            if not target:
                continue

            sheet_path = target if target.startswith("xl/") else f"xl/{target.lstrip('/')}"
            rows = _sheet_rows(zf, sheet_path, shared)

            header_index = -1
            header_keys: list[str | None] = []
            for idx, row in enumerate(rows):
                keys = [_header_key(value) for value in row]
                if sum(key is not None for key in keys) >= 2:
                    header_index = idx
                    header_keys = keys
                    break

            if header_index < 0:
                continue

            headers = rows[header_index]
            for row_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
                if not any(str(value or "").strip() for value in row):
                    continue

                mapping = {
                    str(headers[idx] if idx < len(headers) else f"column_{idx+1}"): (
                        row[idx] if idx < len(row) else ""
                    )
                    for idx in range(max(len(headers), len(row)))
                }
                document = request_document_from_mapping(
                    mapping,
                    source_name=source_name,
                    source_sheet=sheet_name,
                    source_row=row_number,
                )
                if any([
                    document.request_no,
                    document.customer_name,
                    document.total_amount,
                ]):
                    results.append(document)

        return results
