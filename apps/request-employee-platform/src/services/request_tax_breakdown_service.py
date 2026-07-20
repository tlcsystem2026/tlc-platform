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


def _is_zero_placeholder(line: str) -> bool:
    normalized = unicodedata.normalize("NFKC", str(line or ""))
    return bool(
        re.search(
            r"(?:¥|￥|\\)?\s*[-－―ー]\s*$",
            normalized.strip(),
        )
    )


def _detect_section_rate(line: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(line or ""))
    compact = re.sub(r"\s+", "", normalized)

    if re.search(r"(?:①|1)[^\n]{0,20}(?:通常税率|標準税率)", compact):
        return "10"
    if re.search(r"(?:②|2)[^\n]{0,20}(?:軽減税率)", compact):
        return "8"
    if re.search(r"(?:10\s*[%％]|標準税率|通常税率)", normalized):
        return "10"
    if re.search(r"(?:8\s*[%％]|軽減税率)", normalized):
        return "8"
    return ""


def _extract_line(
    result: dict[str, str],
    raw_line: str,
    current_rate: str = "",
) -> str:
    line = unicodedata.normalize("NFKC", str(raw_line or "")).strip()
    if not line:
        return current_rate

    compact = re.sub(r"\s+", "", line)
    detected_rate = _detect_section_rate(line)
    if detected_rate:
        current_rate = detected_rate

    # Non-taxable and exempt amounts are independent from rate sections.
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

    rate = detected_rate or current_rate
    if not rate:
        return current_rate

    rate_pattern = (
        r"(?:10\s*[%％]|標準税率|通常税率)"
        if rate == "10"
        else r"(?:8\s*[%％]|軽減税率)"
    )

    inclusive = (
        _amount_after(
            line,
            rate_pattern + r".{0,30}(?:税込|含税|税込金額|合計)",
        )
        or _amount_after(
            line,
            r"(?:税込|含税|税込金額)" + r".{0,30}" + rate_pattern,
        )
    )
    tax = (
        _amount_after(
            line,
            rate_pattern + r".{0,30}(?:消費税|税額)",
        )
        or _amount_after(
            line,
            r"(?:消費税|税額)" + r".{0,30}" + rate_pattern,
        )
    )
    taxable = (
        _amount_after(
            line,
            rate_pattern + r".{0,30}(?:対象額|課税対象|税抜|対象|小計)",
        )
        or _amount_after(
            line,
            r"(?:対象額|課税対象|税抜|対象|小計)"
            + r".{0,30}"
            + rate_pattern,
        )
    )

    if inclusive:
        _set_if_empty(
            result,
            f"tax_inclusive_amount_{rate}",
            inclusive,
        )
    if tax:
        _set_if_empty(result, f"tax_amount_{rate}", tax)
    if taxable:
        _set_if_empty(result, f"taxable_amount_{rate}", taxable)

    zero_placeholder = _is_zero_placeholder(line)

    if any(
        token in compact
        for token in ("税込額", "税込金額", "含税額", "含税金額")
    ):
        fallback = _last_amount(line)
        if fallback:
            _set_if_empty(
                result,
                f"tax_inclusive_amount_{rate}",
                fallback,
            )
        elif zero_placeholder:
            _set_if_empty(
                result,
                f"tax_inclusive_amount_{rate}",
                "0",
            )
        return current_rate

    if any(token in compact for token in ("消費税", "税額")):
        # A line such as "消費税 8% \\ -" contains the rate digit 8,
        # but no tax amount. Treat the dash as zero instead of 8 yen.
        if zero_placeholder:
            _set_if_empty(result, f"tax_amount_{rate}", "0")
            return current_rate

        fallback = _last_amount(line)
        if fallback and fallback != rate:
            _set_if_empty(result, f"tax_amount_{rate}", fallback)
        return current_rate

    if any(
        token in compact
        for token in (
            "小計(税抜)",
            "小計（税抜）",
            "税抜小計",
            "対象額",
            "課税対象",
            "税抜",
        )
    ):
        if zero_placeholder:
            _set_if_empty(
                result,
                f"taxable_amount_{rate}",
                "0",
            )
            return current_rate

        fallback = _last_amount(line)
        if fallback:
            _set_if_empty(
                result,
                f"taxable_amount_{rate}",
                fallback,
            )
        return current_rate

    return current_rate

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
    current_rate = ""
    for line in normalized.splitlines():
        current_rate = _extract_line(result, line, current_rate)
    return finalize_tax_breakdown(result)


def extract_tax_breakdown_from_excel(
    data: dict[str, Any],
) -> dict[str, str]:
    result = empty_tax_breakdown()
    current_rate = ""

    for sheet in data.get("sheets", []):
        current_rate = ""
        for row in sheet.get("rows", []):
            values = [
                str(cell)
                for cell in row
                if cell not in (None, "")
            ]
            line = " ".join(values)

            # Excel often stores 10%/8% as 0.1/0.08.
            if any(
                token in line
                for token in ("消費税", "税額")
            ):
                for cell in row:
                    if isinstance(cell, (int, float, Decimal)):
                        decimal_value = Decimal(str(cell))
                        if decimal_value == Decimal("0.1"):
                            current_rate = "10"
                        elif decimal_value == Decimal("0.08"):
                            current_rate = "8"

            current_rate = _extract_line(
                result,
                line,
                current_rate,
            )

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
