import base64
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_customer_master_service import (
    ensure_customer_master_table,
    import_todokedl_csv_base64,
)


HEADERS = (
    "お届け先コード,郵便番号,お届け先名称１,お届け先名称２,"
    "お届け先住所１,お届け先住所２,お届け先電話番号,カナ名称,"
    "お届け先Eメールアドレス,JIS市町村コード,出荷通知メール希望区分,荷送人コード\r\n"
)


def _db(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'customer.db'}")
    return sessionmaker(bind=engine)()


def _encoded(text_value: str, encoding: str = "cp932") -> str:
    return base64.b64encode(text_value.encode(encoding)).decode("ascii")


def test_todokedl_cp932_creates_additive_delivery_fields(tmp_path):
    db = _db(tmp_path)
    result = import_todokedl_csv_base64(
        db,
        _encoded(
            HEADERS
            + "666736964,5580055,（株）プラノトレード,,大阪府大阪市住吉区万代,"
              "２－７－３－５０１,666736964,,,27,0,\r\n"
        ),
    )
    assert result == {"imported": 1, "created": 1, "updated": 0, "skipped": 0}
    row = db.execute(text("SELECT * FROM tlc_customer_master")).mappings().one()
    assert row["customer_id"] == "666736964"
    assert row["formal_name"] == ""
    assert row["katakana_name"] == ""
    assert row["katakana_name_short"] == ""
    assert row["delivery_name_1"] == "（株）プラノトレード"
    assert row["delivery_name_2"] == ""


def test_todokedl_update_preserves_formal_names_and_empty_cells(tmp_path):
    db = _db(tmp_path)
    ensure_customer_master_table(db)
    now = "2026-07-19T00:00:00+00:00"
    db.execute(text("""
        INSERT INTO tlc_customer_master (
            id, customer_id, formal_name, katakana_name,
            katakana_name_short, delivery_name_1, delivery_name_2,
            created_at, updated_at
        ) VALUES ('x','C001','株式会社正式名','カブシキガイシャセイシキ',
                  '旧短名','旧配送1','旧配送2',:now,:now)
    """), {"now": now})
    db.commit()
    result = import_todokedl_csv_base64(
        db,
        _encoded(HEADERS + "C001,,新配送1,,,,,新短名,,,,\r\n", "utf-8"),
    )
    assert result["updated"] == 1
    row = db.execute(text("SELECT * FROM tlc_customer_master WHERE customer_id='C001'" )).mappings().one()
    assert row["formal_name"] == "株式会社正式名"
    assert row["katakana_name"] == "カブシキガイシャセイシキ"
    assert row["katakana_name_short"] == "新短名"
    assert row["delivery_name_1"] == "新配送1"
    assert row["delivery_name_2"] == "旧配送2"


def test_todokedl_import_is_atomic(tmp_path):
    db = _db(tmp_path)
    bad = HEADERS + "C001,,配送1,配送2,,,,カナ,,,,\r\n,,配送3,配送4,,,,カナ,,,,\r\n"
    try:
        import_todokedl_csv_base64(db, _encoded(bad))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    ensure_customer_master_table(db)
    assert db.execute(text("SELECT COUNT(*) FROM tlc_customer_master")).scalar_one() == 0


def test_customer_page_exposes_confirmed_mapping():
    page = Path("src/web/static/tlc_customer_master.html").read_text(encoding="utf-8")
    for value in [
        "BUILD037_CUSTOMER_TODOKEDL_R1",
        "katakana_name_short",
        "delivery_name_1",
        "delivery_name_2",
        "/api/tlc-customers/import-todokedl",
    ]:
        assert value in page
