from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_legal_entity_master_service import (
    LegalEntityDeleteConflict,
    delete_entity,
    list_entities,
    save_entity,
    set_default,
)


APP = Path(__file__).parents[1]


def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legal.db'}")
    return sessionmaker(bind=engine)()


def test_crud_default_and_code_level_reference_check(tmp_path, monkeypatch):
    db = session(tmp_path)
    monkeypatch.setenv("TLC_SUPER_ADMIN_OPERATORS", "admin")
    save_entity(db, {"id": "A", "name": "法人A", "operator": "admin"})
    save_entity(db, {"id": "B", "name": "法人B", "operator": "admin"})
    set_default(db, "A", "admin")
    assert [row for row in list_entities(db) if row["id"] == "A"][0]["is_default"] == 1
    db.execute(text("CREATE TABLE business_data(id TEXT,legal_entity_id TEXT)"))
    db.execute(text("INSERT INTO business_data VALUES('1','B')"))
    db.commit()
    try:
        delete_entity(db, "B", "admin", "SUPER_ADMIN")
        assert False, "referenced entity must not be deleted"
    except LegalEntityDeleteConflict as exc:
        assert exc.references[0]["table"] == "business_data"
        assert exc.references[0]["count"] == 1
    db.execute(text("DELETE FROM business_data"));db.commit()
    assert delete_entity(db, "B", "admin", "SUPER_ADMIN")["deleted"] is True


def test_page_routes_and_dashboard_entries_exist():
    page = (APP / "src/web/static/legal_entity_master.html").read_text(encoding="utf-8")
    route = (APP / "src/api/routes/tlc_legal_entity_master.py").read_text(encoding="utf-8")
    main = (APP / "src/main.py").read_text(encoding="utf-8")
    dashboard = (APP / "src/web/static/dashboard.html").read_text(encoding="utf-8")
    system_page = (APP / "src/web/static/system_parameter_center.html").read_text(encoding="utf-8")
    assert "法人主数据维护" in page
    assert '"/legal-entity-master"' in route
    assert "tlc_legal_entity_master_router" in main
    assert "/legal-entity-master" in dashboard
    assert "/legal-entity-master" in system_page


def test_no_foreign_key_is_added():
    service = (APP / "src/services/tlc_legal_entity_master_service.py").read_text(encoding="utf-8").upper()
    assert "FOREIGN KEY" not in service
    assert "PRAGMA TABLE_INFO" in service
