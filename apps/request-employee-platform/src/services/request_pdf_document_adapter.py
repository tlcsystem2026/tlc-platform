from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


FIELD_PATTERNS = {
    "request_no": [
        r"(?:request\s*(?:no|number)|invoice\s*(?:no|number)|请求书编号|請求書番号|請求番号)\s*[:：]?\s*([A-Za-z0-9._/-]+)",
    ],
    "request_date": [
        r"(?:request\s*date|invoice\s*date|请求日期|請求日|発行日)\s*[:：]?\s*([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})",
    ],
    "customer_id": [
        r"(?:customer\s*id|client\s*id|客户\s*id|顧客\s*id|得意先コード)\s*[:：]?\s*([A-Za-z0-9._/-]+)",
    ],
    "customer_name": [
        r"(?:customer\s*name|client\s*name|客户名称|顧客名|得意先名)\s*[:：]?\s*([^\r\n]+)",
    ],
    "currency": [
        r"(?:currency|币种|通貨)\s*[:：]?\s*([A-Za-z]{3})",
    ],
    "subtotal": [
        r"(?:subtotal|sub\s*total|税前金额|小计|小計|税抜金額)\s*[:：]?\s*([¥$€]?\s*[0-9,]+(?:\.[0-9]+)?)",
    ],
    "tax_amount": [
        r"(?:tax\s*amount|tax|税额|消費税)\s*[:：]?\s*([¥$€]?\s*[0-9,]+(?:\.[0-9]+)?)",
    ],
    "total_amount": [
        r"(?:total\s*amount|grand\s*total|total|合计|合計|請求金額|税込金額)\s*[:：]?\s*([¥$€]?\s*[0-9,]+(?:\.[0-9]+)?)",
    ],
}


def _clean_line(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_text(text: str) -> str:
    # Some parser/test integrations provide escaped line separators.
    normalized = (text or "").replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    return "\n".join(_clean_line(line) for line in normalized.splitlines() if _clean_line(line))


def _money(value: str) -> str:
    raw = (value or "").replace(",", "").replace("¥", "").replace("$", "").replace("€", "").strip()
    if not raw:
        return ""
    try:
        return format(Decimal(raw), "f")
    except InvalidOperation:
        return raw


@dataclass(slots=True)
class PdfRequestDocument:
    source_type: str = "pdf"
    source_name: str = ""
    request_no: str = ""
    request_date: str = ""
    customer_id: str = ""
    customer_name: str = ""
    currency: str = ""
    subtotal: str = ""
    tax_amount: str = ""
    total_amount: str = ""
    page_no: int = 0
    raw_text: str = ""

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
            "page_no": self.page_no,
            "raw_text": self.raw_text,
        }


def request_document_from_pdf_text(
    text: str,
    *,
    source_name: str = "request.pdf",
    page_no: int = 0,
) -> PdfRequestDocument:
    normalized = _normalize_text(text)
    values: dict[str, str] = {}

    for field, patterns in FIELD_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, normalized, flags=re.IGNORECASE | re.MULTILINE)
            if match:
                values[field] = _clean_line(match.group(1))
                break

    for money_field in ("subtotal", "tax_amount", "total_amount"):
        if money_field in values:
            values[money_field] = _money(values[money_field])

    return PdfRequestDocument(
        source_name=source_name,
        request_no=values.get("request_no", ""),
        request_date=values.get("request_date", ""),
        customer_id=values.get("customer_id", ""),
        customer_name=values.get("customer_name", ""),
        currency=values.get("currency", ""),
        subtotal=values.get("subtotal", ""),
        tax_amount=values.get("tax_amount", ""),
        total_amount=values.get("total_amount", ""),
        page_no=page_no,
        raw_text=normalized,
    )


def parse_request_document_pdf(
    content: bytes,
    *,
    source_name: str = "request.pdf",
) -> PdfRequestDocument:
    if not content.startswith(b"%PDF"):
        raise ValueError("Invalid PDF content")

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required for PDF request parsing") from exc

    reader = PdfReader(content)
    pages = [page.extract_text() or "" for page in reader.pages]
    merged = "\n".join(pages).strip()

    if not merged:
        raise ValueError("PDF contains no extractable text; image/OCR flow is required")

    return request_document_from_pdf_text(
        merged,
        source_name=source_name,
        page_no=1 if pages else 0,
    )
