from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_dashboard_contains_all_security_administration_entries():
    page = (ROOT / "src/web/static/dashboard.html").read_text(encoding="utf-8")
    required = {
        "/access-control-center": "人员、角色与权限",
        "/super-admin-management": "超级管理员设置",
        "/security-ip-control-center": "IP 访问控制",
        "/security-center": "MFA 与安全审计",
        "/system-parameter-center": "系统参数维护",
        "/my-profile": "我的资料与密码",
    }
    assert "TLC_DASHBOARD_SECURITY_ADMIN_ENTRIES_R2" in page
    for path, title in required.items():
        assert f'href="{path}"' in page
        assert title in page
    assert 'data-required-role="SUPER_ADMIN"' in page


def test_permission_navigation_filters_cards_and_super_admin_role():
    source = (ROOT / "src/services/tlc_api_permission_service.py").read_text(encoding="utf-8")
    assert '"/access-control-center": "USER_PERMISSION"' in source
    assert '"/super-admin-management": "USER_PERMISSION"' in source
    assert '"roles": sorted(roles)' in source
    assert "data-required-role" in source
    assert "dataset.requiredRole" in source
