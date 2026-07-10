from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


COMPARE_FIELDS = (
    "request_no",
    "request_date",
    "customer_id",
    "customer_name",
    "currency",
    "subtotal",
    "tax_amount",
    "total_amount",
)

MONEY_FIELDS = {"subtotal", "tax_amount", "total_amount"}


@dataclass(slots=True)
class RequestDocumentDifference:
    field: str
    excel_value: str
    pdf_value: str
    severity: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(slots=True)
class RequestDocumentCompareResult:
    matched: bool
    request_no: str
    differences: list[RequestDocumentDifference]
    excel_source: str
    pdf_source: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "request_no": self.request_no,
            "differences": [item.as_dict() for item in self.differences],
            "excel_source": self.excel_source,
            "pdf_source": self.pdf_source,
        }


def _as_mapping(document: Any) -> Mapping[str, Any]:
    if isinstance(document, Mapping):
        return document
    if hasattr(document, "as_dict"):
        return document.as_dict()
    if is_dataclass(document):
        return asdict(document)
    raise TypeError(f"Unsupported request document type: {type(document)!r}")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical_decimal(value: Any) -> str:
    raw = _text(value).replace(",", "").replace("¥", "").replace("$", "").replace("€", "")
    if not raw:
        return ""
    try:
        number = Decimal(raw)
    except InvalidOperation:
        return raw

    normalized = number.normalize()
    if normalized == normalized.to_integral():
        return format(normalized.quantize(Decimal("1")), "f")
    return format(normalized, "f")


def _normalized_text(field: str, value: Any) -> str:
    text = _text(value)

    if field in MONEY_FIELDS:
        return _canonical_decimal(text)

    if field == "currency":
        return text.upper()

    if field == "customer_name":
        return " ".join(text.split()).casefold()

    if field == "request_date":
        return text.replace("/", "-").replace(".", "-")

    return text


def _severity(field: str, excel_value: str, pdf_value: str) -> str:
    if field in {"request_no", "total_amount"}:
        return "error"
    if not excel_value or not pdf_value:
        return "warning"
    return "error"


def compare_request_documents(
    excel_document: Any,
    pdf_document: Any,
) -> RequestDocumentCompareResult:
    excel = _as_mapping(excel_document)
    pdf = _as_mapping(pdf_document)

    differences: list[RequestDocumentDifference] = []

    for field in COMPARE_FIELDS:
        excel_value = _text(excel.get(field, ""))
        pdf_value = _text(pdf.get(field, ""))

        if _normalized_text(field, excel_value) == _normalized_text(field, pdf_value):
            continue

        differences.append(
            RequestDocumentDifference(
                field=field,
                excel_value=excel_value,
                pdf_value=pdf_value,
                severity=_severity(field, excel_value, pdf_value),
                message=f"{field} mismatch",
            )
        )

    request_no = _text(excel.get("request_no", "")) or _text(pdf.get("request_no", ""))

    return RequestDocumentCompareResult(
        matched=not differences,
        request_no=request_no,
        differences=differences,
        excel_source=_text(excel.get("source_name", "")),
        pdf_source=_text(pdf.get("source_name", "")),
    )


def to_legacy_compare_payload(result: RequestDocumentCompareResult) -> dict[str, Any]:
    return {
        "request_no": result.request_no,
        "matched": result.matched,
        "difference_count": len(result.differences),
        "differences": [
            {
                "field": item.field,
                "left": item.excel_value,
                "right": item.pdf_value,
                "severity": item.severity,
                "message": item.message,
            }
            for item in result.differences
        ],
        "sources": {
            "excel": result.excel_source,
            "pdf": result.pdf_source,
        },
    }
