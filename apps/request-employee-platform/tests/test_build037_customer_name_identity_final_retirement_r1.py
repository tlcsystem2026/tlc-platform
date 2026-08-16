from pathlib import Path


ROOT = Path(__file__).parents[1]
SRC = ROOT / "src"
FORBIDDEN_EN = "a" + "lias"
FORBIDDEN_ZH = chr(0x522B) + chr(0x540D)


def test_active_source_has_retired_old_customer_name_terms():
    hits = []
    for path in SRC.rglob("*"):
        if path.suffix not in {".py", ".html", ".js"}:
            continue
        value = path.read_text(encoding="utf-8-sig")
        if FORBIDDEN_EN.lower() in value.lower() or FORBIDDEN_ZH in value:
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_name_matching_routes_and_remitter_action_are_current():
    main = (SRC / "main.py").read_text(encoding="utf-8-sig")
    route = (SRC / "api/routes/tlc_customer_name_matching.py").read_text(encoding="utf-8-sig")
    page = (SRC / "web/static/customer_name_matching_center.html").read_text(encoding="utf-8-sig")
    remitter = (SRC / "services/tlc_bank_remitter_candidate_service.py").read_text(encoding="utf-8-sig")
    assert "tlc_customer_name_matching" in main
    assert "/api/tlc-customer-name-matching" in route
    assert "/customer-name-matching-center" in route
    assert "/api/tlc-customer-name-matching" in page
    assert "REGISTER_REMITTER_NAME" in remitter
    assert "name_identity_field" in remitter


def test_registered_names_are_the_single_business_response_field():
    review = (SRC / "services/request_pending_review_service.py").read_text(encoding="utf-8-sig")
    sales = (SRC / "services/formal_sales_ledger_service.py").read_text(encoding="utf-8-sig")
    page = (SRC / "web/static/request_review_workbench.html").read_text(encoding="utf-8-sig")
    assert "master_registered_names" in review
    assert "master_registered_names" in sales
    assert "master_registered_names" in page
