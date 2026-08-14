from pathlib import Path

ROOT = Path(__file__).parents[1]
STATIC = ROOT / "src/web/static"
TARGETS = [
    "security_ip_control_center.html",
    "security_center.html",
    "super_admin_management.html",
    "legal_entity_master.html",
    "system_parameter_center.html",
    "import_center.html",
    "monthly_close_center.html",
]


def test_all_seven_pages_have_unified_list_interaction():
    for name in TARGETS:
        page = (STATIC / name).read_text(encoding="utf-8")
        for contract in ["TLC_SYSTEM_ADMIN_LIST_INTERACTION_R1", "PAGE_SIZE=100", "tlc-list-active", "data-tlc-list-sort", "aria-sort", "综合检索（全字段部分匹配）", "指定字段部分匹配"]:
            assert contract in page, (name, contract)


def test_security_business_contracts_are_preserved():
    ip = (STATIC / "security_ip_control_center.html").read_text(encoding="utf-8")
    security = (STATIC / "security_center.html").read_text(encoding="utf-8")
    admin = (STATIC / "super_admin_management.html").read_text(encoding="utf-8")
    for contract in ["startTest()", "confirmTest()", "cancelMode()", "/api/security-ip-control/enforcement"]:
        assert contract in ip
    for contract in ["setup()", "enable()", "disable()", "stepup()", "revoke("]:
        assert contract in security
    for contract in ["grantAdmin()", "revokeAdmin(", "GRANT_SUPER_ADMIN", "REVOKE_SUPER_ADMIN"]:
        assert contract in admin


def test_master_import_and_monthly_close_contracts_are_preserved():
    combined = "\n".join((STATIC / name).read_text(encoding="utf-8") for name in ["legal_entity_master.html", "system_parameter_center.html", "import_center.html", "monthly_close_center.html"])
    for contract in ["/api/legal-entities", "/api/tlc-system-parameters", "/api/tlc-import-jobs", "/api/tlc-monthly-close"]:
        assert contract in combined
