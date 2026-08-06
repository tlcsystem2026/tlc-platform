from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_system_parameter_is_a_single_unified_card():
    page = (ROOT / "src/web/static/dashboard.html").read_text(encoding="utf-8")
    assert "TLC_DASHBOARD_SECURITY_ADMIN_ENTRIES_R2" in page
    assert page.count('href="/system-parameter-center"') == 1
    assert 'class="navitem" href="/system-parameter-center"' in page
    assert "系统参数维护" in page
    assert "系统基础配置与核查" not in page
    section = page.split('id="security-administration-entries"', 1)[1].split("</section>", 1)[0]
    assert 'href="/system-parameter-center"' in section


def test_system_parameter_navigation_uses_module_permission():
    source = (ROOT / "src/services/tlc_api_permission_service.py").read_text(encoding="utf-8")
    assert '"/system-parameter-center": "SYSTEM_PARAMETER"' in source
    assert '(r"/system-parameter-center", "SYSTEM_PARAMETER", "VIEW")' in source
