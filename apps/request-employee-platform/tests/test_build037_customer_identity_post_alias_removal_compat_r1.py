from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_customer_master_service import list_customers, save_customer
from src.services.tlc_customer_legacy_alias_removal_service import remove_legacy_alias_columns

ROOT=Path(__file__).parents[1]


def test_customer_api_projection_comes_from_identity_table_after_column_removal(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'post-alias.db'}")
    Session=sessionmaker(bind=engine)
    with Session() as db:
        customer=save_customer(db,{"customer_id":"C001","formal_name":"三友貿易株式会社","alias_1":"三友贸易(株)"})
        result=remove_legacy_alias_columns(db,actor="TEST")
        assert result["ready_for_column_removal"] is True
        columns={row[1] for row in db.execute(text("PRAGMA table_info(tlc_customer_master)"))}
        assert "alias_1" not in columns
        rows=list_customers(db,customer_id="C001")
        assert rows[0]["id"] == customer["id"]
        assert "三友贸易(株)" in rows[0]["registered_names"]


def test_bank_customer_reference_uses_registered_names_only():
    page=(ROOT/"src/web/static/bank_remitter_candidate_center.html").read_text(encoding="utf-8")
    assert "registered_names" in page
    assert "[x.alias_1" not in page


def test_business_sources_do_not_query_physical_alias_columns():
    allowed={
        "tlc_customer_master_service.py",
        "tlc_customer_name_identity_service.py",
        "tlc_customer_legacy_alias_removal_service.py",
    }
    for path in (ROOT/"src/services").glob("*.py"):
        if path.name in allowed:
            continue
        text_value=path.read_text(encoding="utf-8")
        assert "alias_1" not in text_value or "master_alias_1" in text_value, path.name
