from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any


BREAKDOWN_FIELDS = (
    "taxable_amount_10",
    "tax_amount_10",
    "tax_inclusive_amount_10",
    "taxable_amount_8",
    "tax_amount_8",
    "tax_inclusive_amount_8",
    "non_taxable_amount",
    "tax_exempt_amount",
)

COMPARE_CODES = {
    "taxable_amount_10": "TAXABLE_AMOUNT_10_MISMATCH",
    "tax_amount_10": "TAX_AMOUNT_10_MISMATCH",
    "tax_inclusive_amount_10": "TAX_INCLUSIVE_AMOUNT_10_MISMATCH",
    "taxable_amount_8": "TAXABLE_AMOUNT_8_MISMATCH",
    "tax_amount_8": "TAX_AMOUNT_8_MISMATCH",
    "tax_inclusive_amount_8": "TAX_INCLUSIVE_AMOUNT_8_MISMATCH",
    "non_taxable_amount": "NON_TAXABLE_AMOUNT_MISMATCH",
    "tax_exempt_amount": "TAX_EXEMPT_AMOUNT_MISMATCH",
}

_AMOUNT = r"(?:¥|￥|\\)?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.\d{1,2})?"


def empty_tax_breakdown() -> dict[str, str]:
    result = {field: "" for field in BREAKDOWN_FIELDS}
    result.update(
        {
            "calculated_subtotal": "",
            "calculated_tax_amount": "",
            "calculated_total_amount": "",
        }
    )
    return result


def amount_string(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"))).rstrip("0").rstrip(".")


def parse_amount(value: Any) -> str:
    text_value = unicodedata.normalize("NFKC", str(value or ""))
    match = re.search(_AMOUNT, text_value)
    if not match:
        return ""
    try:
        return amount_string(Decimal(match.group(1).replace(",", "")))
    except InvalidOperation:
        return ""


def _last_amount(value: str) -> str:
    matches = re.findall(_AMOUNT, value)
    if not matches:
        return ""
    try:
        return amount_string(Decimal(matches[-1].replace(",", "")))
    except InvalidOperation:
        return ""


def _set_if_empty(result: dict[str, str], key: str, value: str) -> None:
    if value and not result.get(key):
        result[key] = value


def _amount_after(line: str, pattern: str) -> str:
    match = re.search(pattern + r"[^0-9¥￥\\]{0,40}" + _AMOUNT, line, re.I)
    if not match:
        return ""
    try:
        return amount_string(Decimal(match.group(1).replace(",", "")))
    except InvalidOperation:
        return ""


def _extract_line(result: dict[str, str], raw_line: str) -> None:
    line = unicodedata.normalize("NFKC", str(raw_line or "")).strip()
    if not line:
        return

    compact = re.sub(r"\s+", "", line)

    # Non-taxable and exempt amounts are independent from rate-based lines.
    if "非課税" in compact:
        _set_if_empty(
            result,
            "non_taxable_amount",
            _amount_after(line, r"非\s*課\s*税") or _last_amount(line),
        )
    if "免税" in compact:
        _set_if_empty(
            result,
            "tax_exempt_amount",
            _amount_after(line, r"免\s*税") or _last_amount(line),
        )

    rate = ""
    if re.search(r"(?:10\s*[%％]|標準税率)", line):
        rate = "10"
    elif re.search(r"(?:8\s*[%％]|軽減税率)", line):
        rate = "8"
    if not rate:
        return

    rate_pattern = (
        r"(?:10\s*[%％]|標準税率)"
        if rate == "10"
        else r"(?:8\s*[%％]|軽減税率)"
    )

    # Prefer explicit label/value patterns on the same line.
    inclusive = (
        _amount_after(line, rate_pattern + r".{0,30}(?:税込|含税|税込金額|合計)")
        or _amount_after(line, r"(?:税込|含税|税込金額)" + r".{0,30}" + rate_pattern)
    )
    tax = (
        _amount_after(line, rate_pattern + r".{0,30}(?:消費税|税額)")
        or _amount_after(line, r"(?:消費税|税額)" + r".{0,30}" + rate_pattern)
    )
    taxable = (
        _amount_after(line, rate_pattern + r".{0,30}(?:対象額|課税対象|税抜|対象)")
        or _amount_after(line, r"(?:対象額|課税対象|税抜|対象)" + r".{0,30}" + rate_pattern)
    )

    if inclusive:
        _set_if_empty(result, f"tax_inclusive_amount_{rate}", inclusive)
    if tax:
        _set_if_empty(result, f"tax_amount_{rate}", tax)
    if taxable:
        _set_if_empty(result, f"taxable_amount_{rate}", taxable)

    # A common layout has one label per row/line. Classify the last amount.
    fallback = _last_amount(line)
    if not fallback:
        return

    if any(token in compact for token in ("税込", "含税")):
        _set_if_empty(result, f"tax_inclusive_amount_{rate}", fallback)
    elif any(token in compact for token in ("消費税", "税額")):
        _set_if_empty(result, f"tax_amount_{rate}", fallback)
    elif any(token in compact for token in ("対象額", "課税対象", "税抜", "対象")):
        _set_if_empty(result, f"taxable_amount_{rate}", fallback)


def _decimal(value: str) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _sum_present(values: list[str]) -> str:
    decimals = [_decimal(value) for value in values]
    actual = [value for value in decimals if value is not None]
    if not actual:
        return ""
    return amount_string(sum(actual, Decimal("0")))


def finalize_tax_breakdown(result: dict[str, str]) -> dict[str, str]:
    subtotal = _sum_present(
        [
            result.get("taxable_amount_10", ""),
            result.get("taxable_amount_8", ""),
            result.get("non_taxable_amount", ""),
            result.get("tax_exempt_amount", ""),
        ]
    )
    tax_amount = _sum_present(
        [
            result.get("tax_amount_10", ""),
            result.get("tax_amount_8", ""),
        ]
    )

    inclusive_values = [
        result.get("tax_inclusive_amount_10", ""),
        result.get("tax_inclusive_amount_8", ""),
    ]
    inclusive_total = _sum_present(inclusive_values)
    extras = _sum_present(
        [
            result.get("non_taxable_amount", ""),
            result.get("tax_exempt_amount", ""),
        ]
    )

    total = ""
    if inclusive_total:
        values = [inclusive_total]
        if extras:
            values.append(extras)
        total = _sum_present(values)
    elif subtotal:
        values = [subtotal]
        if tax_amount:
            values.append(tax_amount)
        total = _sum_present(values)

    result["calculated_subtotal"] = subtotal
    result["calculated_tax_amount"] = tax_amount
    result["calculated_total_amount"] = total
    return result


def extract_tax_breakdown_from_text(value: str) -> dict[str, str]:
    result = empty_tax_breakdown()
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    for line in normalized.splitlines():
        _extract_line(result, line)
    return finalize_tax_breakdown(result)


def extract_tax_breakdown_from_excel(data: dict[str, Any]) -> dict[str, str]:
    result = empty_tax_breakdown()
    for sheet in data.get("sheets", []):
        for row in sheet.get("rows", []):
            line = " ".join(
                str(cell)
                for cell in row
                if cell not in (None, "")
            )
            _extract_line(result, line)
    return finalize_tax_breakdown(result)


def has_tax_breakdown(value: dict[str, str]) -> bool:
    return any(value.get(field) not in (None, "") for field in BREAKDOWN_FIELDS)


def compare_tax_breakdowns(
    pdf_value: dict[str, str],
    excel_value: dict[str, str],
) -> tuple[list[str], list[str]]:
    codes: list[str] = []
    details: list[str] = []

    pdf_has = has_tax_breakdown(pdf_value)
    excel_has = has_tax_breakdown(excel_value)

    if pdf_has != excel_has:
        codes.append("TAX_BREAKDOWN_MISSING")
        details.append(
            "Tax-rate breakdown exists in only one of PDF/Excel"
        )
        return codes, details

    if not pdf_has and not excel_has:
        return codes, details

    for field in BREAKDOWN_FIELDS:
        pdf_amount = str(pdf_value.get(field, "") or "")
        excel_amount = str(excel_value.get(field, "") or "")
        if pdf_amount and excel_amount and pdf_amount != excel_amount:
            codes.append(COMPARE_CODES[field])
            details.append(
                f"{field}: PDF={pdf_amount}, Excel={excel_amount}"
            )
        elif bool(pdf_amount) != bool(excel_amount):
            codes.append("TAX_BREAKDOWN_MISSING")
            details.append(
                f"{field} exists in only one of PDF/Excel"
            )

    # De-duplicate while preserving order.
    return list(dict.fromkeys(codes)), list(dict.fromkeys(details))
