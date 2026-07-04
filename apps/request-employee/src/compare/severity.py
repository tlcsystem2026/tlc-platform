from decimal import Decimal

def classify_difference(field: str, pdf_value: str, excel_value: str) -> str:
    critical_fields = {"request_no", "total_amount", "amount", "quantity", "unit_price"}
    warning_fields = {"customer_name", "request_date", "product_name", "product_code"}

    if field in critical_fields:
        return "ERROR"
    if field in warning_fields:
        return "WARNING"
    return "INFO"

def money_equal(a, b, tolerance=Decimal("0")) -> bool:
    try:
        return abs(Decimal(str(a)) - Decimal(str(b))) <= tolerance
    except Exception:
        return str(a).strip() == str(b).strip()
