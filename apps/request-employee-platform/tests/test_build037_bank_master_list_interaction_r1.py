from pathlib import Path

PAGE = Path("src/web/static/tlc_bank_account_master.html")

def test_bank_and_account_lists_share_interaction_contract():
    page = PAGE.read_text(encoding="utf-8")
    for value in ("TLC_BANK_MASTER_LIST_INTERACTION_R1", "sortMasterList", "list-row-active", "listPageSize=100", "aria-sort", 'type+"ListPager"', 's.direction==="asc"'):
        assert value in page

def test_selection_does_not_scroll_and_checkboxes_remain_independent():
    enhanced = PAGE.read_text(encoding="utf-8").split("TLC_BANK_MASTER_LIST_INTERACTION_R1", 1)[1]
    assert "scrollTo(" not in enhanced
    assert "event.stopPropagation()" in enhanced

def test_business_search_and_sort_keys_are_present():
    page = PAGE.read_text(encoding="utf-8")
    for value in ("bankFilterCode", "bankFilterName", "filterBank", "filterBranchCode", "filterBranchName", "filterAccount", "filterAccountHolder", "filterAdapterCode", '"account_number"', '"adapter_code"'):
        assert value in page
