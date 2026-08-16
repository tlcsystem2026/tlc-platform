from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_customer_identity_audit_service import (
    FORMAL_BACKFILL_CONFIRMATION,
    backfill_missing_formal_identities,
    scan_conflicts,
)
from src.services.tlc_customer_name_identity_service import TABLE


ROOT = Path(__file__).parents[1]


def make_db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'formal.db').as_posix()}")
    db = sessionmaker(bind=engine)()
    db.execute(text("""CREATE TABLE tlc_customer_master(
      id TEXT PRIMARY KEY,customer_id TEXT NOT NULL,formal_name TEXT NOT NULL,
      active INTEGER NOT NULL DEFAULT 1)"""))
    db.execute(text("INSERT INTO tlc_customer_master(id,customer_id,formal_name,active) VALUES"
                    "('r1','C001','Customer One',1),('r2','C002','Customer Two',1)"))
    db.commit()
    return engine, db


def test_formal_identity_backfill_is_backed_up_and_audited(tmp_path):
    engine, db = make_db(tmp_path)
    try:
        result = backfill_missing_formal_identities(db, "admin", FORMAL_BACKFILL_CONFIRMATION)
        assert result["missing_before"] == 2
        assert result["created"] == 2
        assert result["remaining"] == 0
        assert Path(result["backup_path"]).is_file()
        rows = db.execute(text(f"SELECT customer_id,name_type,source_system FROM {TABLE} ORDER BY customer_id")).all()
        assert [tuple(row) for row in rows] == [
            ("C001", "FORMAL", "CUSTOMER_MASTER"),
            ("C002", "FORMAL", "CUSTOMER_MASTER"),
        ]
        assert scan_conflicts(db)["counts"].get("MISSING_FORMAL_IDENTITY", 0) == 0
    finally:
        db.close()
        engine.dispose()


def test_formal_identity_backfill_requires_actor_and_confirmation(tmp_path):
    engine, db = make_db(tmp_path)
    try:
        for actor, confirmation in [("", FORMAL_BACKFILL_CONFIRMATION), ("admin", "wrong")]:
            try:
                backfill_missing_formal_identities(db, actor, confirmation)
            except ValueError:
                pass
            else:
                raise AssertionError("Validation should reject this request")
    finally:
        db.close()
        engine.dispose()


def test_page_and_route_expose_controlled_batch_backfill():
    page = (ROOT / "src/web/static/customer_identity_audit_center.html").read_text(encoding="utf-8-sig")
    route = (ROOT / "src/api/routes/tlc_customer_identity_audit.py").read_text(encoding="utf-8-sig")
    assert "backfillFormalButton" in page
    assert "BACKFILL_FORMAL_IDENTITIES" in page
    assert "/api/customer-identity-audit/backfill-formal" in page
    assert "/api/customer-identity-audit/backfill-formal" in route
