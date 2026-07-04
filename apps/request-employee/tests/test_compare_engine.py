from decimal import Decimal
from models.request import RequestDocument
from compare.compare_engine import CompareEngine

def test_total_difference():
    a = RequestDocument(request_no="LY01006", total_amount=Decimal("100"))
    b = RequestDocument(request_no="LY01006", total_amount=Decimal("101"))
    diffs = CompareEngine().compare(a, b)
    assert any(x["field"] == "total_amount" for x in diffs)
