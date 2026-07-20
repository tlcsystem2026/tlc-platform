from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_bank_account_profile_service import (
    BankDeleteConflict,
    delete_banks,
    delete_profiles,
    ensure_table as ensure_bank_table,
)
from src.services.tlc_customer_master_service import (
    MasterDeleteConflict,
    delete_customers,
    ensure_customer_master_table,
)


def session(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'delete.sqlite3').as_posix()}"
    )
    return engine, sessionmaker(bind=engine)()


def test_customer_delete_blocks_associated_data_and_is_atomic(tmp_path):
    engine, db = session(tmp_path)
    try:
        ensure_customer_master_table(db)
        db.execute(text("""
            INSERT INTO tlc_customer_master(
                id,customer_id,formal_name,hiragana_name,katakana_name,
                short_name,alias_1,alias_2,alias_3,alias_4,alias_5,
                normalized_formal_name,status_code,active,note,created_at,updated_at
            ) VALUES(
                'c1','C001','Customer 1','','','','','','','','',
                'customer1','ACTIVE',1,'','now','now'
            )
        """))
        db.execute(text("""
            INSERT INTO tlc_customer_master(
                id,customer_id,formal_name,hiragana_name,katakana_name,
                short_name,alias_1,alias_2,alias_3,alias_4,alias_5,
                normalized_formal_name,status_code,active,note,created_at,updated_at
            ) VALUES(
                'c2','C002','Customer 2','','','','','','','','',
                'customer2','ACTIVE',1,'','now','now'
            )
        """))
        db.execute(text(
            "CREATE TABLE business_link("
            "id TEXT PRIMARY KEY, customer_id TEXT)"
        ))
        db.execute(text(
            "INSERT INTO business_link(id,customer_id) VALUES('b1','C001')"
        ))
        db.commit()

        with pytest.raises(MasterDeleteConflict):
            delete_customers(db, ["c1", "c2"])

        assert db.execute(
            text("SELECT COUNT(*) FROM tlc_customer_master")
        ).scalar_one() == 2

        result = delete_customers(db, ["c2"])
        assert result["deleted"] == 1
    finally:
        db.close()
        engine.dispose()


def test_bank_delete_order_and_association_rules(tmp_path):
    engine, db = session(tmp_path)
    try:
        ensure_bank_table(db)
        db.execute(text("""
            INSERT INTO tlc_code_value(
                id,category_code,code,name_zh,name_ja,name_en,
                sort_order,active,extra_json,created_at,updated_at
            ) VALUES(
                'bank1','BANK','BANK_X','Bank X','Bank X','Bank X',
                1,1,'{}','now','now'
            )
        """))
        db.execute(text("""
            INSERT INTO tlc_bank_account_profile(
                id,bank_code,branch_code,branch_name,account_type,
                account_number,account_holder,adapter_code,file_encoding,
                active,note,created_at,updated_at
            ) VALUES(
                'account1','BANK_X','','','','12345','','','cp932',
                1,'','now','now'
            )
        """))
        db.commit()

        with pytest.raises(BankDeleteConflict):
            delete_banks(db, ["bank1"])

        assert delete_profiles(db, ["account1"])["deleted"] == 1
        assert delete_banks(db, ["bank1"])["deleted"] == 1
    finally:
        db.close()
        engine.dispose()


def test_delete_buttons_and_endpoints_are_present():
    root = Path(__file__).parents[1]
    customer_page = (
        root / "src/web/static/tlc_customer_master.html"
    ).read_text(encoding="utf-8")
    bank_page = (
        root / "src/web/static/tlc_bank_account_master.html"
    ).read_text(encoding="utf-8")
    customer_route = (
        root / "src/api/routes/tlc_customer_master.py"
    ).read_text(encoding="utf-8")
    bank_route = (
        root / "src/api/routes/tlc_bank_account_profile.py"
    ).read_text(encoding="utf-8")

    for required in [
        "删除当前客户",
        "批量删除所选客户",
        "/api/tlc-customers/delete-batch",
    ]:
        assert required in customer_page or required in customer_route

    for required in [
        "删除当前银行",
        "删除当前账户",
        "批量删除所选银行",
        "批量删除所选账户",
        "/api/tlc-banks/delete-batch",
        "/api/tlc-bank-accounts/delete-batch",
    ]:
        assert required in bank_page or required in bank_route
