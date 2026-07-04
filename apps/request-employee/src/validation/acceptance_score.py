from __future__ import annotations
from decimal import Decimal

WEIGHTS = {
    "request_no": 20,
    "request_date": 10,
    "customer_name": 15,
    "total_amount": 25,
    "line_count": 20,
    "difference_quality": 10,
}

def acceptance_score(pdf_doc, excel_doc, diffs: list[dict]) -> dict:
    score = 0
    checks = {}

    checks["request_no"] = bool(pdf_doc.request_no and excel_doc.request_no)
    checks["request_date"] = bool(pdf_doc.request_date and excel_doc.request_date)
    checks["customer_name"] = bool(pdf_doc.customer_name and excel_doc.customer_name)
    checks["total_amount"] = (
        Decimal(str(pdf_doc.total_amount)) > 0 and Decimal(str(excel_doc.total_amount)) > 0
    )
    checks["line_count"] = len(pdf_doc.lines) > 0 and len(excel_doc.lines) > 0
    checks["difference_quality"] = all(
        d.get("field") and d.get("severity") and d.get("status") for d in diffs
    )

    for key, ok in checks.items():
        if ok:
            score += WEIGHTS[key]

    if score >= 90:
        grade = "PILOT_READY"
    elif score >= 75:
        grade = "REVIEW"
    else:
        grade = "NOT_READY"

    return {"score": score, "grade": grade, "checks": checks}
