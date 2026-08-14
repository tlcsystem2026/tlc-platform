from pathlib import Path

ROOT = Path(__file__).parents[1]
PAGE = ROOT / "src/web/static/customer_reconciliation_workbench.html"


def test_all_four_reconciliation_lists_are_covered():
    page = PAGE.read_text(encoding="utf-8")
    assert "TLC_CUSTOMER_RECONCILIATION_LIST_INTERACTION_R1" in page
    for body_id in ["salesBody", "paymentBody", "exceptionBody", "historyBody"]:
        assert f'"{body_id}"' in page
    for contract in ["recon-active", "data-recon-sort", "aria-sort", "PAGE_SIZE=100", "综合检索（全字段部分匹配）", "指定字段部分匹配"]:
        assert contract in page


def test_customer_search_requests_all_rows():
    page = PAGE.read_text(encoding="utf-8")
    assert 'p.set("limit","0")' in page


def test_reconciliation_business_actions_are_preserved():
    page = PAGE.read_text(encoding="utf-8")
    for contract in ["runBankMatching()", "calculate()", "confirmResult()", "/api/customer-payment-reconciliation/confirm", "/api/customer-bank-matching/run"]:
        assert contract in page
