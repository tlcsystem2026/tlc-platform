from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services import request_batch_compare_import_service as service


def test_recipient_before_gochu_has_priority_over_invoice_issuer(tmp_path: Path):
    excel = tmp_path / "sample.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet["B5"] = "さばいさばいストア"
    sheet["H5"] = "御中"
    sheet["H6"] = "東京恋人株式会社"
    sheet["H7"] = "T9011401020619"
    workbook.save(excel)
    workbook.close()

    data = service._extract_excel(excel)
    assert service._likely_customer(data) == "さばいさばいストア"


def test_customer_master_delivery_name_can_match_recipient(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'customer.sqlite3').as_posix()}"
    )
    db = sessionmaker(bind=engine)()
    try:
        db.execute(text("""
            CREATE TABLE tlc_customer_master(
                id TEXT PRIMARY KEY,
                customer_id TEXT,
                formal_name TEXT,
                hiragana_name TEXT,
                katakana_name TEXT,
                katakana_name_short TEXT,
                short_name TEXT,
                delivery_name_1 TEXT,
                delivery_name_2 TEXT,
                alias_1 TEXT,
                alias_2 TEXT,
                alias_3 TEXT,
                alias_4 TEXT,
                alias_5 TEXT
            )
        """))
        db.execute(text("""
            INSERT INTO tlc_customer_master(
                id,customer_id,formal_name,hiragana_name,katakana_name,
                katakana_name_short,short_name,delivery_name_1,
                delivery_name_2,alias_1,alias_2,alias_3,alias_4,alias_5
            ) VALUES(
                '1','C001','正式客户名','','','','',
                'さばいさばいストア','','','','','',''
            )
        """))
        db.commit()

        code, name, status = service._match_customer(
            db,
            "さばいさばいストア",
        )
        assert code == "C001"
        assert name == "正式客户名"
        assert status == "MATCHED"
    finally:
        db.close()
        engine.dispose()
