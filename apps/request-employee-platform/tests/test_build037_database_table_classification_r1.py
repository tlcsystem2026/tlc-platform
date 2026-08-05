from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from src.services.tlc_database_maintenance_service import clear_table, list_tables, restore_table_backup, table_classification


def test_five_categories_and_safe_default():
    assert table_classification("tlc_user_master")["category_code"] == "SYSTEM_MAINTENANCE"
    assert table_classification("system_parameter_code")["category_code"] == "FUNCTION_MASTER"
    assert table_classification("tlc_permission_audit")["category_code"] == "AUDIT_HISTORY"
    assert table_classification("tlc_customer_master")["category_code"] == "BUSINESS_MASTER"
    assert table_classification("formal_sales_request_ledger")["category_code"] == "BUSINESS_TRANSACTION"
    unknown = table_classification("unexpected_table_xyz")
    assert unknown["category_code"] == "UNCLASSIFIED"
    assert unknown["can_backup"] is True and unknown["can_restore"] is False and unknown["can_clear"] is False


def test_list_exposes_policy_and_protected_clear(tmp_path, monkeypatch):
    monkeypatch.setenv("TLC_SUPER_ADMIN_OPERATORS", "root-admin")
    engine = create_engine(f"sqlite:///{tmp_path / 'classification.sqlite3'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE tlc_permission_audit(id TEXT PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE tlc_customer_master(id TEXT PRIMARY KEY)"))
    items = {item["table_name"]: item for item in list_tables(engine)}
    assert items["tlc_permission_audit"]["can_clear"] is False
    assert items["tlc_customer_master"]["can_clear"] is True
    with pytest.raises(ValueError, match="AUDIT_HISTORY"):
        clear_table(engine, "tlc_permission_audit", "root-admin", "SUPER_ADMIN", "test", "CLEAR TABLE tlc_permission_audit")


def test_page_contract():
    page = (Path(__file__).parents[1] / "src/web/static/database_maintenance_center.html").read_text(encoding="utf-8")
    for value in ("数据表分类与维护边界", "categoryFilter", "维护说明", "renderTableRows"):
        assert value in page
