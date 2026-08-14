from pathlib import Path


PAGE = Path("src/web/static/tlc_customer_master.html")


def test_customer_list_interaction_contract():
    page = PAGE.read_text(encoding="utf-8")
    for contract in [
        "TLC_CUSTOMER_LIST_INTERACTION_R1",
        "customer-row-active",
        "sortCustomerList",
        "customerListSortDirection",
        'aria-sort',
        "customerListPageSize=100",
        "customerPageInfo",
        "selectCustomerListRow",
        "无最大件数限制",
    ]:
        assert contract in page


def test_customer_list_does_not_scroll_on_row_selection():
    page = PAGE.read_text(encoding="utf-8")
    enhanced = page.split("TLC_CUSTOMER_LIST_INTERACTION_R1", 1)[1]
    assert "scrollTo(" not in enhanced
    assert "event.stopPropagation()" in enhanced


def test_customer_key_columns_are_sortable_and_searchable():
    page = PAGE.read_text(encoding="utf-8")
    for key in [
        "customer_id",
        "formal_name",
        "katakana_name",
        "delivery_name_1",
        "postal_code",
        "status_code",
        "source_system",
    ]:
        assert key in page
    for search_id in [
        "query",
        "searchCustomerId",
        "searchFormalName",
        "searchKatakanaName",
        "searchDeliveryName1",
        "searchPostalCode",
        "searchStatusCode",
    ]:
        assert search_id in page
