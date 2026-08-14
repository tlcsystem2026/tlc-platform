import csv
import io
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services import tlc_bank_remitter_candidate_service as service
from src.services.tlc_customer_master_service import save_customer


ROOT = Path(__file__).parents[1]


def database(tmp_path):
    return sessionmaker(bind=create_engine(f"sqlite:///{tmp_path / 'review_csv.db'}"))()


def seed(db):
    service.ensure_schema(db)
    customer = save_customer(db, {
        "customer_id": "CUST-CSV-001",
        "formal_name": "CSV审核客户",
        "active": True,
    })
    stamp = service.now()
    db.execute(text(f"""INSERT INTO {service.BATCH_TABLE}
      (id,business_month,operator,status,started_at,completed_at,bank_code,source_name)
      VALUES('batch-1','','tester','COMPLETED',:stamp,:stamp,'SUGAMO_SHINKIN','bank.csv')"""), {"stamp": stamp})
    db.execute(text(f"""INSERT INTO {service.CANDIDATE_TABLE}
      (id,candidate_batch_id,business_month,raw_remitter_name,normalized_remitter_name,
       bank_codes,created_at,updated_at)
      VALUES('candidate-1','batch-1','','振込人A','振込人A','SUGAMO_SHINKIN',:stamp,:stamp)"""), {"stamp": stamp})
    db.commit()
    return customer


def csv_bytes(**overrides):
    row = {
        "id": "candidate-1",
        "candidate_batch_id": "batch-1",
        "bank_codes": "SUGAMO_SHINKIN",
        "raw_remitter_name": "振込人A",
        "normalized_remitter_name": "振込人A",
        "transaction_count": "1",
        "total_amount": "100",
        "first_transaction_date": "2026-08-01",
        "last_transaction_date": "2026-08-01",
        "match_status": "WAIT_REVIEW",
        "matched_customer_id": "CUST-CSV-001",
        "matched_customer_name": "CSV审核客户",
        "review_status": "WAIT_REVIEW",
        "resolution_action": "CONFIRM_MATCH",
        "review_comment": "offline checked",
    }
    row.update(overrides)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")


def test_export_and_atomic_import_only_store_review_draft(tmp_path):
    db = database(tmp_path)
    seed(db)
    exported = service.export_review_csv(service.list_candidates(db, batch_id="batch-1"))
    assert exported.startswith(b"\xef\xbb\xbf")
    assert "resolution_action" in exported.decode("utf-8-sig")

    result = service.import_review_csv(db, csv_bytes(), "reviewer")
    assert result == {"updated": 1, "errors": []}
    row = db.execute(text(f"SELECT * FROM {service.CANDIDATE_TABLE} WHERE id='candidate-1'")).mappings().one()
    assert row["matched_customer_id"] == "CUST-CSV-001"
    assert row["matched_customer_name"] == "CSV审核客户"
    assert row["resolution_action"] == "CONFIRM_MATCH"
    assert row["review_comment"] == "offline checked"
    assert row["review_status"] == "WAIT_REVIEW"
    assert row["reviewed_at"] == ""


def test_import_rejects_identity_mismatch_without_partial_update(tmp_path):
    db = database(tmp_path)
    seed(db)
    with pytest.raises(ValueError, match="candidate_batch_id does not match"):
        service.import_review_csv(db, csv_bytes(candidate_batch_id="wrong"), "reviewer")
    row = db.execute(text(f"SELECT resolution_action,review_comment FROM {service.CANDIDATE_TABLE} WHERE id='candidate-1'")).one()
    assert tuple(row) == ("", "")


def test_page_has_csv_review_and_formal_name_first_with_pagination():
    page = (ROOT / "src/web/static/bank_remitter_candidate_center.html").read_text(encoding="utf-8")
    route = (ROOT / "src/api/routes/tlc_bank_remitter_candidate.py").read_text(encoding="utf-8")
    assert "TLC_BANK_REMITTER_CANDIDATE_CSV_REVIEW_R1" in page
    assert "导出候选 CSV" in page
    assert "导入审核结果 CSV" in page
    select = page.split('id="customerFieldQuery"', 1)[1].split("</select>", 1)[0]
    assert select.index('value="formal_name"') < select.index('value="customer_id"')
    assert 'customerFieldQuery.value="formal_name"' in page
    assert 'limit:"0"' in page
    assert "CUSTOMER_PAGE_SIZE=100" in page
    assert "customerPageTo" in page
    assert "/api/bank-remitter-candidates/export.csv" in route
    assert "/api/bank-remitter-candidates/import.csv" in route
