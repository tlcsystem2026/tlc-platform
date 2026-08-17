from pathlib import Path

ROOT=Path(__file__).parents[1]
PAGE=ROOT/"src/web/static/bank_remitter_candidate_center.html"

def test_action_refresh_preserves_candidate_position():
    page=PAGE.read_text(encoding="utf-8")
    for value in (
        "TLC_BANK_REMITTER_ACTION_POSITION_R2",
        'id="candidateScroll"',
        "captureCandidatePosition",
        "restoreCandidatePosition",
        "loadCandidates({preserve:true,activeId:id})",
        "function applyCandidateView()",
        "candidatePreservePage=preserve",
    ):
        assert value in page

def test_bulk_action_refreshes_once_after_all_requests():
    page=PAGE.read_text(encoding="utf-8")
    block=page.split("async function bulkAction(action)",1)[1].split("function openCustomerReference",1)[0]
    assert "resolveOne(id,action,false)" in block
    assert block.count("await loadCandidates") == 1

def test_row_controls_stop_click_bubbling():
    page=PAGE.read_text(encoding="utf-8")
    assert 'onclick="event.stopPropagation()" onchange="updateSelected()"' in page
    assert page.count("event.stopPropagation();resolveOne") == 3
    assert "event.stopPropagation();openCustomerReference" in page
