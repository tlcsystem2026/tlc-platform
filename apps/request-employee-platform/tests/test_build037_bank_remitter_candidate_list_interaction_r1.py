from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "src/web/static/bank_remitter_candidate_center.html"
ROUTE = ROOT / "src/api/routes/tlc_bank_remitter_candidate.py"
SERVICE = ROOT / "src/services/tlc_bank_remitter_candidate_service.py"


def test_candidate_list_has_search_sort_highlight_and_pagination():
    page = PAGE.read_text(encoding="utf-8")
    assert "TLC_BANK_REMITTER_CANDIDATE_LIST_INTERACTION_R1" in page
    for contract in (
        'id="candidateQuery"',
        'id="remitterQuery"',
        'id="assignedCustomerQuery"',
        'id="matchStatusQuery"',
        'class="sortable"',
        "sortCandidates('raw_remitter_name')",
        "selectCandidateRow(",
        "active-row",
        "CANDIDATE_PAGE_SIZE=100",
        "candidatePageTo(",
        'id="candidatePageInfo"',
    ):
        assert contract in page


def test_candidate_page_requests_all_rows_and_service_supports_zero_limit():
    page = PAGE.read_text(encoding="utf-8")
    route = ROUTE.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")
    assert 'limit:"0"' in page
    assert "Query(5000, ge=0, le=10000)" in route
    assert "list_candidates(db, status=status, batch_id=batch_id, limit=0)" in route
    assert "if requested_limit > 0:" in service
    assert 'limit_sql = " LIMIT :limit"' in service


def test_existing_csv_and_customer_reference_contracts_remain():
    page = PAGE.read_text(encoding="utf-8")
    for contract in (
        "TLC_BANK_REMITTER_CANDIDATE_CSV_REVIEW_R1",
        "TLC_BANK_REMITTER_CUSTOMER_REFERENCE_R2",
        "function exportCsv()",
        "function importCsv()",
        'customerFieldQuery.value="formal_name"',
        "CUSTOMER_PAGE_SIZE=100",
    ):
        assert contract in page
