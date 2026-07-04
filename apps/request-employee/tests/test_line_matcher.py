from models.request import RequestLine
from compare.line_matcher import LineMatcher

def test_match_by_product_code():
    p=[RequestLine(1,product_code="A001",product_name="X")]
    e=[RequestLine(1,product_code="A001",product_name="Changed")]
    pairs=LineMatcher().match(p,e)
    assert pairs[0][1] is e[0]
