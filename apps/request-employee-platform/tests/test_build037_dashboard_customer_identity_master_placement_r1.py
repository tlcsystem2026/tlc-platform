from pathlib import Path

ROOT=Path(__file__).parents[1]


def test_identity_entries_are_once_and_inside_base_master_section():
    page=(ROOT/"src/web/static/dashboard.html").read_text(encoding="utf-8")
    assert "TLC_DASHBOARD_CUSTOMER_IDENTITY_MASTER_PLACEMENT_R1" in page
    assert page.count('href="/customer-name-identity-center"') == 1
    assert page.count('href="/customer-identity-audit-center"') == 1
    base=page.index("① 基础主数据")
    next_section=page.index("② 请求书与正式销售",base)
    for href in ("/customer-name-identity-center","/customer-identity-audit-center"):
        assert base < page.index(href) < next_section


def test_identity_entries_are_not_dynamic_navigator_items():
    service=(ROOT/"src/services/dashboard_service.py").read_text(encoding="utf-8")
    assert "/customer-name-identity-center" not in service
    assert "/customer-identity-audit-center" not in service
