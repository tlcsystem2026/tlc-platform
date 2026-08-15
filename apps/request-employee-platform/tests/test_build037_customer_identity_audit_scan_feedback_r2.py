from pathlib import Path

PAGE=Path(__file__).parents[1]/"src/web/static/customer_identity_audit_center.html"

def test_scan_has_visible_progress_and_completion_feedback():
    page=PAGE.read_text(encoding="utf-8")
    for contract in (
        "TLC_CUSTOMER_IDENTITY_AUDIT_SCAN_FEEDBACK_R2",
        "scanStatus", "扫描中", "扫描完成", "button.disabled=true",
        "aria-live", "window.scan",
    ):
        assert contract in page
