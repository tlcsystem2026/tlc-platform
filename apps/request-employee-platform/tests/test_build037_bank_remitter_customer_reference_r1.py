from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_remitter_candidate_has_customer_reference_picker():
    page = (ROOT / "src/web/static/bank_remitter_candidate_center.html").read_text(encoding="utf-8")
    assert "TLC_BANK_REMITTER_CUSTOMER_REFERENCE_R1" in page
    assert 'id="customerReferenceModal"' in page
    assert "客户参照／选择" in page
    assert "openCustomerReference" in page
    assert "searchCustomers" in page
    assert 'api("/api/tlc-customers?"+q)' in page
    assert 'q.set("query"' in page
    assert 'q.set("customer_id"' in page
    assert 'q.set("formal_name"' in page
    assert "delivery_name_1" in page
    assert "registered_names" in page
    assert "chooseCustomer" in page
    assert "decodeURIComponent" in page
    assert '>参照</button>' in page
