from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_bank_remitter_candidate_service import ensure_schema, list_candidates
from src.services.tlc_customer_master_service import save_customer

ROOT = Path(__file__).parents[1]


def test_candidate_list_resolves_current_customer_formal_name(tmp_path):
    db = sessionmaker(bind=create_engine(f"sqlite:///{tmp_path / 'remitter-name.sqlite3'}"))()
    ensure_schema(db)
    customer = save_customer(db, {"customer_id": "CUST-NAME-001", "formal_name": "当前客户正式名称"})
    db.execute(text("""INSERT INTO tlc_bank_remitter_candidate(
      id,candidate_batch_id,business_month,raw_remitter_name,normalized_remitter_name,
      matched_customer_id,matched_customer_name,created_at,updated_at)
      VALUES('candidate-1','batch-1','','REMITTER','REMITTER',:customer,'','now','now')"""),
      {"customer": customer["customer_id"]})
    db.commit()
    rows = list_candidates(db, batch_id="batch-1")
    assert len(rows) == 1
    assert rows[0]["matched_customer_id"] == "CUST-NAME-001"
    assert rows[0]["matched_customer_name"] == "当前客户正式名称"


def test_missing_customer_keeps_historical_name_snapshot(tmp_path):
    db = sessionmaker(bind=create_engine(f"sqlite:///{tmp_path / 'remitter-snapshot.sqlite3'}"))()
    ensure_schema(db)
    db.execute(text("""INSERT INTO tlc_bank_remitter_candidate(
      id,candidate_batch_id,business_month,raw_remitter_name,normalized_remitter_name,
      matched_customer_id,matched_customer_name,created_at,updated_at)
      VALUES('candidate-2','batch-2','','REMITTER','REMITTER','OLD-001','历史客户名称','now','now')"""))
    db.commit()
    rows = list_candidates(db, batch_id="batch-2")
    assert rows[0]["matched_customer_name"] == "历史客户名称"


def test_page_displays_assigned_customer_id_and_name():
    page = (ROOT / "src/web/static/bank_remitter_candidate_center.html").read_text(encoding="utf-8")
    assert "TLC_BANK_REMITTER_ASSIGNED_CUSTOMER_NAME_R1" in page
    assert "matched_customer_id" in page
    assert "matched_customer_name" in page
    assert "客户名称：" in page
