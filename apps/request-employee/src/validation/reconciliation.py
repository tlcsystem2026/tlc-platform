from decimal import Decimal

def D(v):
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")

def reconcile(doc, tolerance="0"):
    """
    Tokyo Koibito invoice lines are tax-included amounts.
    Therefore:
    - sum(line.amount) should reconcile to total_amount, not tax-excluded subtotal.
    - subtotal + tax_amount should reconcile to total_amount when subtotal/tax exist.
    - quantity * unit_price should reconcile to line.amount.
    """
    tol = D(tolerance)
    issues = []

    line_sum = sum((D(x.amount) for x in doc.lines), Decimal("0"))
    subtotal = D(getattr(doc, "subtotal", 0))
    tax_amount = D(getattr(doc, "tax_amount", 0))
    total = D(getattr(doc, "total_amount", 0))

    if doc.lines and total > 0 and abs(line_sum - total) > tol:
        issues.append({
            "rule": "LINE_SUM_VS_TOTAL_TAX_INCLUDED",
            "expected": str(line_sum),
            "actual": str(total),
            "severity": "ERROR",
            "message": "税込商品行合計と請求合計が一致しません。",
        })

    if subtotal > 0 and total > 0 and abs((subtotal + tax_amount) - total) > tol:
        issues.append({
            "rule": "SUBTOTAL_PLUS_TAX_VS_TOTAL",
            "expected": str(subtotal + tax_amount),
            "actual": str(total),
            "severity": "ERROR",
            "message": "税抜小計＋消費税と請求合計が一致しません。",
        })

    for line in doc.lines:
        expected = D(line.quantity) * D(line.unit_price)
        if D(line.amount) > 0 and abs(expected - D(line.amount)) > tol:
            issues.append({
                "rule": "QTY_X_PRICE_VS_AMOUNT",
                "line_no": line.line_no,
                "expected": str(expected),
                "actual": str(line.amount),
                "severity": "WARNING",
                "message": "数量×単価と行金額が一致しません。",
            })

    return issues
