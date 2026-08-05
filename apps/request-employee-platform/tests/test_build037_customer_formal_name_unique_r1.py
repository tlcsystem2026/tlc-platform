from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_customer_master_service import (
    duplicate_formal_name_groups,
    import_customer_rows,
    save_customer,
)


def _db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'customer_formal_name_unique.sqlite3'}",
        connect_args={"check_same_thread": False},
    )
    return sessionmaker(bind=engine)()


def test_manual_save_rejects_typographic_duplicate(tmp_path):
    db = _db(tmp_path)
    first = save_customer(
        db,
        {"customer_id": "UNIQUE-001", "formal_name": "株式会社 テスト商事"},
    )

    try:
        save_customer(
            db,
            {"customer_id": "UNIQUE-002", "formal_name": "株式会社　テスト商事"},
        )
        raise AssertionError("duplicate formal_name was accepted")
    except ValueError as exc:
        assert "formal_name already exists" in str(exc)
        assert "UNIQUE-001" in str(exc)

    updated = save_customer(
        db,
        {
            "id": first["id"],
            "customer_id": "UNIQUE-001",
            "formal_name": "株式会社 テスト商事",
            "note": "self update is allowed",
        },
    )
    assert updated["note"] == "self update is allowed"


def test_import_rejects_duplicate_before_writing(tmp_path):
    db = _db(tmp_path)
    try:
        import_customer_rows(
            db,
            [
                {"customer_id": "IMPORT-001", "formal_name": "合同会社ABC"},
                {"customer_id": "IMPORT-002", "formal_name": "合同会社 AＢＣ"},
            ],
        )
        raise AssertionError("duplicate import was accepted")
    except ValueError as exc:
        assert "duplicate formal_name in import" in str(exc)

    count = db.execute(
        text("SELECT COUNT(*) FROM tlc_customer_master WHERE customer_id LIKE 'IMPORT-%'")
    ).scalar_one()
    assert count == 0


def test_different_legal_entity_names_are_not_collapsed(tmp_path):
    db = _db(tmp_path)
    save_customer(db, {"customer_id": "LEGAL-001", "formal_name": "ABC株式会社"})
    save_customer(db, {"customer_id": "LEGAL-002", "formal_name": "ABC合同会社"})
    assert duplicate_formal_name_groups(db) == []


def test_existing_duplicates_are_reported_without_deletion(tmp_path):
    db = _db(tmp_path)
    save_customer(db, {"customer_id": "AUDIT-001", "formal_name": "監査株式会社"})
    db.execute(text("DROP INDEX ux_tlc_customer_master_formal_name_unique_key"))
    db.execute(
        text(
            "INSERT INTO tlc_customer_master "
            "(id,customer_id,formal_name,formal_name_unique_key,created_at,updated_at) "
            "VALUES ('audit-2','AUDIT-002','監査 株式会社','監査株式会社','now','now')"
        )
    )
    db.commit()

    groups = duplicate_formal_name_groups(db)
    assert len(groups) == 1
    assert {row["customer_id"] for row in groups[0]["customers"]} == {
        "AUDIT-001",
        "AUDIT-002",
    }
