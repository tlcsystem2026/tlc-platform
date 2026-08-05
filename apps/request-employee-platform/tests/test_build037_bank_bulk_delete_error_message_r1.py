from pathlib import Path


def test_bank_page_preserves_structured_delete_conflict():
    page = (
        Path(__file__).parents[1]
        / "src/web/static/tlc_bank_account_master.html"
    ).read_text(encoding="utf-8")
    assert "error.detail=detail" in page
    assert "error.status=response.status" in page
    assert "item.name_zh||item.name_ja||item.account_holder" in page
    assert "${r.table}.${r.column}：${r.count}件" in page
    assert "[object Object]" not in page


def test_bank_batch_delete_keeps_atomic_business_rule():
    page = (
        Path(__file__).parents[1]
        / "src/web/static/tlc_bank_account_master.html"
    ).read_text(encoding="utf-8")
    assert "/api/tlc-banks/delete-batch" in page
    assert "任一银行有关联时整批不删除" in page
