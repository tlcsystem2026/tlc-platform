from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_customer_master_service import save_customer
from src.services.tlc_customer_name_identity_service import match_name, register_name
from src.services.tlc_customer_candidate_service import _match_customer_identity, _customers
from src.services.tlc_customer_identity_migration_service import migration_plan, migrate_customer_only


def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'identity.db'}")
    return sessionmaker(bind=engine)(), engine


def test_chinese_and_japanese_request_names_map_to_one_customer(tmp_path):
    db, _ = session(tmp_path)
    customer = save_customer(db, {"customer_id": "CUST-ISE", "formal_name": "伊勢彩堂株式会社"})
    register_name(db, customer_record_id=customer["id"], customer_id=customer["customer_id"],
                  name_value="伊势彩堂株式会社", name_type="REQUEST_NAME", language_code="zh",
                  actor="tester")
    assert match_name(db, "伊勢彩堂株式会社")["customer_id"] == "CUST-ISE"
    result = match_name(db, "伊势彩堂株式会社")
    assert result["customer_id"] == "CUST-ISE"
    assert result["name_type"] == "REQUEST_NAME"
    match = _match_customer_identity(db, "伊势彩堂株式会社", _customers(db))
    assert match["customer"]["customer_id"] == "CUST-ISE"


def test_same_active_name_cannot_belong_to_two_customers(tmp_path):
    db, _ = session(tmp_path)
    first = save_customer(db, {"customer_id": "C1", "formal_name": "甲株式会社"})
    second = save_customer(db, {"customer_id": "C2", "formal_name": "乙株式会社"})
    register_name(db, customer_record_id=first["id"], customer_id="C1",
                  name_value="共同名称", name_type="REQUEST_NAME")
    try:
        register_name(db, customer_record_id=second["id"], customer_id="C2",
                      name_value="共同名称", name_type="REQUEST_NAME")
    except ValueError as exc:
        assert "already assigned" in str(exc)
    else:
        raise AssertionError("duplicate active customer identity was accepted")


def test_customer_only_migration_preserves_master_and_security_and_clears_business(tmp_path):
    db, engine = session(tmp_path)
    customer = save_customer(db, {"customer_id": "C1", "formal_name": "甲株式会社"})
    db.execute(text("CREATE TABLE tlc_user_master(id TEXT PRIMARY KEY)"))
    db.execute(text("INSERT INTO tlc_user_master VALUES('U1')"))
    db.execute(text("CREATE TABLE formal_sales_request_ledger(id TEXT PRIMARY KEY,customer_id TEXT)"))
    db.execute(text("INSERT INTO formal_sales_request_ledger VALUES('S1','C1')"))
    db.commit()
    plan = migration_plan(db)
    assert "tlc_customer_master" in plan["preserved_tables"]
    assert "formal_sales_request_ledger" in plan["clear_tables"]
    result = migrate_customer_only(db, "MIGRATE_CUSTOMER_ONLY_AND_CLEAR_BUSINESS_DATA", "tester")
    assert result["cleared_tables"]["formal_sales_request_ledger"] == 1
    assert db.execute(text("SELECT COUNT(*) FROM tlc_customer_master")).scalar_one() == 1
    assert db.execute(text("SELECT COUNT(*) FROM tlc_user_master")).scalar_one() == 1
    assert match_name(db, "甲株式会社")["customer_record_id"] == customer["id"]
