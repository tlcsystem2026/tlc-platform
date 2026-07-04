from decimal import Decimal
from parser.normalizer import normalize_money, clean_text

def test_normalize_money():
    assert normalize_money("￥12,345") == Decimal("12345")

def test_clean_text():
    assert clean_text(" A \n B ") == "A B"
