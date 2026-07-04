from decimal import Decimal
from models.request import RequestDocument, RequestLine
from validation.acceptance_score import acceptance_score

def test_pilot_ready_score():
    p=RequestDocument(
        request_no="LY01006",request_date="2026-01-01",
        customer_name="顧客",total_amount=Decimal("100"),
        lines=[RequestLine(1,product_name="A",amount=Decimal("100"))]
    )
    e=RequestDocument(
        request_no="LY01006",request_date="2026-01-01",
        customer_name="顧客",total_amount=Decimal("100"),
        lines=[RequestLine(1,product_name="A",amount=Decimal("100"))]
    )
    result=acceptance_score(p,e,[])
    assert result["score"] >= 90
    assert result["grade"] == "PILOT_READY"
