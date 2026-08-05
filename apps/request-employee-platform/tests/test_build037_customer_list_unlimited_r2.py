from pathlib import Path


APP = Path(__file__).parents[1]


def test_customer_api_has_no_default_row_cap():
    source = (APP / "src/api/routes/tlc_customer_master.py").read_text(encoding="utf-8")
    assert "limit:int=Query(0,ge=0)" in source
    assert "include_inactive=include_inactive,limit=0)" in source


def test_customer_service_only_limits_when_explicitly_requested():
    source = (APP / "src/services/tlc_customer_master_service.py").read_text(encoding="utf-8")
    assert "include_inactive:bool=True,limit:int=0" in source
    assert "min(max(int(limit),1),2000)" not in source
    assert "if int(limit or 0)>0:" in source


def test_customer_page_labels_complete_result():
    page = (APP / "src/web/static/tlc_customer_master.html").read_text(encoding="utf-8")
    assert "件（全部）" in page
    assert "无最大件数限制" in page
