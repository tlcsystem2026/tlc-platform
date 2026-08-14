from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "src/web/static/bank_remitter_candidate_center.html"


def test_sort_heading_shows_direction_indicator_and_accessible_state():
    page = PAGE.read_text(encoding="utf-8")
    assert "TLC_BANK_REMITTER_CANDIDATE_SORT_INDICATOR_R2" in page
    for contract in (
        "function updateSortIndicators()",
        'candidateSortDirection===1?"↑":"↓"',
        'th.setAttribute("aria-sort",active?direction:"none")',
        'th.classList.toggle("sort-asc"',
        'th.classList.toggle("sort-desc"',
        'indicator.className="sort-indicator"',
        "updateSortIndicators()",
    ):
        assert contract in page


def test_sort_indicator_preserves_list_interaction_r1():
    page = PAGE.read_text(encoding="utf-8")
    assert "TLC_BANK_REMITTER_CANDIDATE_LIST_INTERACTION_R1" in page
    assert "function sortCandidates(key)" in page
    assert "function applyCandidateView()" in page
    assert "CANDIDATE_PAGE_SIZE=100" in page
