from pathlib import Path

ROOT = Path(__file__).parents[1]
PAGE = ROOT / "src/web/static/database_maintenance_center.html"


def test_database_maintenance_lists_have_common_interactions():
    page = PAGE.read_text(encoding="utf-8")
    for contract in ["TLC_DATABASE_MAINTENANCE_LIST_INTERACTION_R1", "PAGE_SIZE=100", "db-active", "data-db-sort", "aria-sort", "综合检索（全字段部分匹配）", "指定字段部分匹配"]:
        assert contract in page
    for body_id in ["tableRows", "backupRows", "auditRows"]:
        assert f'"{body_id}"' in page


def test_database_risk_and_classification_contracts_are_preserved():
    page = PAGE.read_text(encoding="utf-8")
    for contract in ["categoryFilter", "risk_level", "can_backup", "can_restore", "can_clear", "maintenance_note"]:
        assert contract in page


def test_high_risk_business_actions_are_preserved():
    page = PAGE.read_text(encoding="utf-8")
    for contract in ["fullBackup()", "fullRestore()", "tableBackup()", "tableRestore()", "tableClear()", "SUPER_ADMIN", "请先填写维护理由"]:
        assert contract in page
