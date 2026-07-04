from decimal import Decimal

def D(v):
    try: return Decimal(str(v))
    except Exception: return Decimal("0")

def reconcile(doc, tolerance="0"):
    tol=D(tolerance); issues=[]
    line_sum=sum((D(x.amount) for x in doc.lines),Decimal("0"))
    if doc.lines and abs(line_sum-D(doc.subtotal))>tol:
        issues.append({"rule":"LINE_SUM_VS_SUBTOTAL","expected":str(line_sum),"actual":str(doc.subtotal),"severity":"ERROR"})
    calculated=D(doc.subtotal)+D(doc.tax_amount)
    if D(doc.total_amount)>0 and abs(calculated-D(doc.total_amount))>tol:
        issues.append({"rule":"SUBTOTAL_PLUS_TAX_VS_TOTAL","expected":str(calculated),"actual":str(doc.total_amount),"severity":"ERROR"})
    for line in doc.lines:
        expected=D(line.quantity)*D(line.unit_price)
        if abs(expected-D(line.amount))>tol:
            issues.append({"rule":"QTY_X_PRICE_VS_AMOUNT","line_no":line.line_no,"expected":str(expected),"actual":str(line.amount),"severity":"WARNING"})
    return issues
