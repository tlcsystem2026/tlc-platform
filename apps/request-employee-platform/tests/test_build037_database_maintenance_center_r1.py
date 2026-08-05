from pathlib import Path

from sqlalchemy import create_engine, text

from src.services.tlc_database_maintenance_service import (
    AUDIT_TABLE,
    clear_table,
    create_full_backup,
    create_table_backup,
    list_audit,
    list_backups,
    list_tables,
    restore_full_backup,
    restore_table_backup,
)


def _engine(tmp_path, monkeypatch):
    monkeypatch.setenv("TLC_SUPER_ADMIN_OPERATORS", "root-admin")
    monkeypatch.setenv("TLC_DATABASE_MAINTENANCE_BACKUP_DIR", str(tmp_path / "backups"))
    engine = create_engine(f"sqlite:///{tmp_path / 'application.sqlite3'}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE customers (id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE)"
        ))
        connection.execute(text("INSERT INTO customers VALUES ('C1','Customer One')"))
    return engine


def test_full_backup_and_restore(tmp_path, monkeypatch):
    engine = _engine(tmp_path, monkeypatch)
    backup = create_full_backup(engine, "root-admin", "SUPER_ADMIN", "before test")
    assert Path(tmp_path / "backups" / backup["file_name"]).exists()

    with engine.begin() as connection:
        connection.execute(text("INSERT INTO customers VALUES ('C2','Customer Two')"))
    result = restore_full_backup(
        engine,
        backup["backup_id"],
        "root-admin",
        "SUPER_ADMIN",
        "restore test",
        "RESTORE DATABASE",
    )
    assert result["status"] == "restored"
    with engine.connect() as connection:
        assert connection.execute(text("SELECT id FROM customers ORDER BY id")).scalars().all() == ["C1"]
    assert any(row["action"] == "FULL_RESTORE" for row in list_audit(engine))


def test_table_backup_clear_and_restore(tmp_path, monkeypatch):
    engine = _engine(tmp_path, monkeypatch)
    backup = create_table_backup(engine, "customers", "root-admin", "SUPER_ADMIN", "table snapshot")
    cleared = clear_table(
        engine,
        "customers",
        "root-admin",
        "SUPER_ADMIN",
        "clear test data",
        "CLEAR TABLE customers",
    )
    assert cleared["deleted_rows"] == 1
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM customers")).scalar_one() == 0

    restored = restore_table_backup(
        engine,
        "customers",
        backup["backup_id"],
        "root-admin",
        "SUPER_ADMIN",
        "restore table",
        "RESTORE TABLE customers",
    )
    assert restored["row_count"] == 1
    assert any(item["backup_type"] == "TABLE" for item in list_backups())
    tables = {item["table_name"]: item for item in list_tables(engine)}
    assert tables["customers"]["row_count"] == 1
    assert tables["customers"]["table_description"]
    assert tables[AUDIT_TABLE]["protected"] is True


def test_super_admin_and_confirmation_are_required(tmp_path, monkeypatch):
    engine = _engine(tmp_path, monkeypatch)
    try:
        create_full_backup(engine, "ordinary-user", "SUPER_ADMIN", "test")
        raise AssertionError("unconfigured administrator was accepted")
    except PermissionError:
        pass
    try:
        clear_table(
            engine,
            "customers",
            "root-admin",
            "SUPER_ADMIN",
            "test",
            "wrong confirmation",
        )
        raise AssertionError("wrong confirmation was accepted")
    except ValueError as exc:
        assert "CLEAR TABLE customers" in str(exc)


def test_page_contract():
    page = (
        Path(__file__).parents[1]
        / "src/web/static/database_maintenance_center.html"
    ).read_text(encoding="utf-8")
    for required in (
        "BUILD037_DATABASE_MAINTENANCE_CENTER_R1",
        "整体备份与恢复",
        "单表备份与恢复",
        "单表数据清除（超级管理员）",
        "RESTORE DATABASE",
        "CLEAR TABLE",
        "中文说明",
    ):
        assert required in page
