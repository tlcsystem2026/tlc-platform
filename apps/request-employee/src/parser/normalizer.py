from decimal import Decimal, InvalidOperation
import re

def clean_text(value) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()

def normalize_money(value) -> Decimal:
    s = clean_text(value).replace(",", "").replace("¥", "").replace("￥", "")
    s = re.sub(r"[^\d.\-]", "", s)
    if not s or s in {"-", ".", "-."}:
        return Decimal("0")
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")

def normalize_key(value) -> str:
    return clean_text(value).lower().replace(" ", "")
