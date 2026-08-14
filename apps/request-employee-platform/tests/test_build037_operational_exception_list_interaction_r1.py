from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_exception_page_has_list_interactions():
    page = (ROOT / "src/web/static/operational_exception_dashboard.html").read_text(encoding="utf-8")
    for contract in ["TLC_OPERATIONAL_EXCEPTION_LIST_INTERACTION_R1", "EXCEPTION_PAGE_SIZE=100", "exception-active", "data-sort-key", "aria-sort", 'id="exceptionKeyword"', 'id="exceptionStatus"', 'id="exceptionTitle"', 'limit:"0"']:
        assert contract in page


def test_existing_exception_filters_are_preserved():
    page = (ROOT / "src/web/static/operational_exception_dashboard.html").read_text(encoding="utf-8")
    for contract in ["businessMonth", "severityFilter", "categoryFilter", "/api/tlc-operational-exceptions"]:
        assert contract in page


def test_exception_api_supports_unlimited_result():
    route = (ROOT / "src/api/routes/tlc_operational_exception_dashboard.py").read_text(encoding="utf-8")
    service = (ROOT / "src/services/tlc_operational_exception_dashboard_service.py").read_text(encoding="utf-8")
    assert "Query(default=0, ge=0)" in route
    assert "query_limit = requested_limit if requested_limit > 0 else -1" in service
    assert "if requested_limit > 0:" in service
