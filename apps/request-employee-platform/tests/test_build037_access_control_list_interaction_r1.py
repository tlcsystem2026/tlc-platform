from pathlib import Path

ROOT = Path(__file__).parents[1]
PAGE = ROOT / "src/web/static/access_control_center.html"


def test_access_control_lists_have_common_interactions():
    page = PAGE.read_text(encoding="utf-8")
    for contract in ["TLC_ACCESS_CONTROL_LIST_INTERACTION_R1", "PAGE_SIZE=100", "acl-active", "data-acl-sort", "aria-sort", "综合检索（全字段部分匹配）", "指定字段部分匹配"]:
        assert contract in page
    for body_id in ["userRows", "departmentRows", "permissionRows", "auditRows"]:
        assert f'"{body_id}"' in page


def test_permission_and_role_business_functions_are_preserved():
    page = PAGE.read_text(encoding="utf-8")
    for contract in ["saveUser()", "saveUserRoles()", "savePermissionMatrix()", "/api/access-control/users", "/api/access-control/roles/"]:
        assert contract in page


def test_super_admin_is_not_added_to_normal_role_assignment():
    page = PAGE.read_text(encoding="utf-8")
    assert "/api/super-admin/grant" not in page
    assert "GRANT_SUPER_ADMIN" not in page
