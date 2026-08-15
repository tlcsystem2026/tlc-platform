from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.customer_bank_name_matching_service import match_customer_by_bank_counterparty
from src.services.tlc_customer_master_service import list_customers, save_customer
from src.services.tlc_customer_name_identity_service import migrate_legacy_aliases, register_name


def _db(tmp_path):
    return sessionmaker(bind=create_engine(f"sqlite:///{tmp_path/'legacy-alias.db'}"))()


def test_legacy_aliases_are_migrated_and_searchable(tmp_path):
    db = _db(tmp_path)
    customer = save_customer(db, {"customer_id": "C1", "formal_name": "Formal", "alias_1": "Legacy Alias"})
    db.execute(text("DELETE FROM tlc_customer_name_identity WHERE name_type='HISTORICAL'")); db.commit()
    result = migrate_legacy_aliases(db)
    assert result["created"] == 1 and result["conflict_count"] == 0
    assert list_customers(db, query="Legacy Alias")[0]["id"] == customer["id"]


def test_bank_matching_prefers_name_identity(tmp_path):
    db = _db(tmp_path)
    customer = save_customer(db, {"customer_id": "C2", "formal_name": "Bank Customer"})
    register_name(db, customer_record_id=customer["id"], customer_id="C2",
                  name_value="BANK REMITTER XYZ", name_type="BANK_REMITTER")
    matched = match_customer_by_bank_counterparty(db, "BANK REMITTER XYZ")
    assert matched.status == "MATCHED"
    assert matched.customer_id == "C2"
    assert matched.matched_field == "NAME_IDENTITY_BANK_REMITTER"


def test_customer_page_no_longer_edits_legacy_alias_columns():
    from pathlib import Path
    page = Path("src/web/static/tlc_customer_master.html").read_text(encoding="utf-8")
    assert "TLC_CUSTOMER_LEGACY_ALIAS_RETIREMENT_R1" in page
    assert "removeLegacyAliasEditors" in page
    assert "['alias1','alias2','alias3','alias4','alias5']" in page
