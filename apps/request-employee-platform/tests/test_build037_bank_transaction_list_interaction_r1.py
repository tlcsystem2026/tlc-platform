from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_bank_transaction_page_has_common_list_interactions():
    page = (ROOT / "src/web/static/bank_import.html").read_text(encoding="utf-8")
    for contract in [
        "TLC_BANK_TRANSACTION_LIST_INTERACTION_R1",
        'id="txKeyword"',
        'id="txAccountSearch"',
        'id="txDescriptionSearch"',
        'data-sort-key="transaction_date"',
        'aria-sort',
        "TX_PAGE_SIZE=100",
        "is-active",
        'p.set("limit","0")',
    ]:
        assert contract in page


def test_existing_bank_import_contract_is_preserved():
    page = (ROOT / "src/web/static/bank_import.html").read_text(encoding="utf-8")
    for contract in ["importBankCode", "selected_bank_code", "/api/bank-import/csv", "handleImportBankChange"]:
        assert contract in page


def test_bank_transaction_api_accepts_unlimited_and_service_has_optional_limit():
    route = (ROOT / "src/api/routes/bank_import_ui.py").read_text(encoding="utf-8")
    service = (ROOT / "src/services/bank_transaction_query_service.py").read_text(encoding="utf-8")
    assert "Query(default=0, ge=0)" in route
    assert 'limit_sql = ""' in service
    assert "if requested_limit > 0" in service
