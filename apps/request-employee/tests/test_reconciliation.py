from decimal import Decimal
from models.request import RequestDocument,RequestLine
from validation.reconciliation import reconcile

def test_line_sum_issue():
    d=RequestDocument(subtotal=Decimal("99"),total_amount=Decimal("99"),lines=[RequestLine(1,quantity=Decimal("1"),unit_price=Decimal("100"),amount=Decimal("100"))])
    issues=reconcile(d)
    assert any(x["rule"]=="LINE_SUM_VS_SUBTOTAL" for x in issues)

def test_qty_price_issue():
    d=RequestDocument(lines=[RequestLine(1,quantity=Decimal("2"),unit_price=Decimal("10"),amount=Decimal("19"))])
    issues=reconcile(d)
    assert any(x["rule"]=="QTY_X_PRICE_VS_AMOUNT" for x in issues)
