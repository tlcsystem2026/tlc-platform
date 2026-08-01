from pathlib import Path


def test_customer_bulk_delete_reads_rendered_checkbox_ids():
    page = Path("src/web/static/tlc_customer_master.html").read_text(encoding="utf-8")
    assert 'class="ck customer-row-check"' in page
    assert 'value="${esc(r.id)}"' in page
    assert '#rows input.customer-row-check:checked' in page
    assert '.row-check:checked' not in page
    assert "body:JSON.stringify({ids})" in page


def test_customer_select_all_targets_same_checkbox_family():
    page = Path("src/web/static/tlc_customer_master.html").read_text(encoding="utf-8")
    assert "document.querySelectorAll('.ck')" in page
    assert "x.checked=v" in page
