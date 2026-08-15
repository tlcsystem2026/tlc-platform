from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_customer_legacy_alias_removal_service import (
    CONTRACT,
    LEGACY_ALIAS_COLUMNS,
    remove_legacy_alias_columns,
)


def test_alias_columns_are_migrated_and_physically_removed(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'alias-removal.db'}")
    Session=sessionmaker(bind=engine)
    with Session() as db:
        db.execute(text("""CREATE TABLE tlc_customer_master(
          id TEXT PRIMARY KEY,customer_id TEXT,formal_name TEXT,active INTEGER,
          alias_1 TEXT,alias_2 TEXT,alias_3 TEXT,alias_4 TEXT,alias_5 TEXT)"""))
        db.execute(text("""INSERT INTO tlc_customer_master VALUES(
          'r1','C001','伊勢彩株式会社',1,'ISESAI','','','','')"""))
        db.commit()
        result=remove_legacy_alias_columns(db,actor="TEST")
        columns={row[1] for row in db.execute(text("PRAGMA table_info(tlc_customer_master)"))}
        assert not columns.intersection(LEGACY_ALIAS_COLUMNS)
        assert result["removed"] == list(LEGACY_ALIAS_COLUMNS)
        identity=db.execute(text("""SELECT customer_id,name_value,name_type
          FROM tlc_customer_name_identity WHERE name_value='ISESAI'""")).one()
        assert tuple(identity) == ("C001","ISESAI","HISTORICAL")
        assert remove_legacy_alias_columns(db)["already_removed"] is True
    assert CONTRACT == "TLC_CUSTOMER_LEGACY_ALIAS_COLUMNS_REMOVAL_R1"
