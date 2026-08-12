from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services import tlc_bank_remitter_candidate_service as service
from src.services.multi_bank_csv_import_service import BankTransaction


ROOT = Path(__file__).parents[1]


def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'candidate_csv.db'}")
    return sessionmaker(bind=engine)()


def transaction(direction, counterparty, amount, tx_id):
    return BankTransaction(
        bank_code="SUGAMO_SHINKIN", bank_name="Sugamo", account_number="1",
        transaction_id=tx_id, transaction_date="2026-08-12",
        deposit_amount=amount if direction == "CREDIT" else "",
        withdrawal_amount=amount if direction == "DEBIT" else "",
        amount=amount, direction=direction, counterparty=counterparty,
        description="", balance="", source_file="raw.csv", import_batch_id="preview",
    )


def test_extracts_directly_from_csv_without_importing_bank_transactions(tmp_path, monkeypatch):
    db = db_session(tmp_path)
    monkeypatch.setattr(service, "detect_bank_csv", lambda _content: "SUGAMO_SHINKIN")
    monkeypatch.setattr(service, "parse_bank_csv", lambda *_args, **_kwargs: [
        transaction("CREDIT", "ABC REMITTER", "100", "x1"),
        transaction("CREDIT", "ABC REMITTER", "200", "x2"),
        transaction("DEBIT", "NOT A REMITTER", "50", "x3"),
    ])
    batch = service.run_extraction_from_csv(
        db, b"original-csv", "SUGAMO_SHINKIN", "raw.csv", "tester"
    )
    assert batch["bank_code"] == "SUGAMO_SHINKIN"
    assert batch["source_name"] == "raw.csv"
    assert batch["transaction_count"] == 2
    rows = service.list_candidates(db, batch_id=batch["id"])
    assert len(rows) == 1
    assert rows[0]["raw_remitter_name"] == "ABC REMITTER"
    assert rows[0]["transaction_count"] == 2
    assert rows[0]["total_amount"] == "300"
    assert db.execute(text("SELECT COUNT(*) FROM bank_transaction_import")).scalar_one() == 0


def test_rejects_wrong_selected_bank_before_parse_or_batch(tmp_path, monkeypatch):
    db = db_session(tmp_path)
    monkeypatch.setattr(service, "detect_bank_csv", lambda _content: "JAPAN_POST_BANK")
    monkeypatch.setattr(service, "parse_bank_csv", lambda *_args, **_kwargs: pytest.fail("must not parse"))
    with pytest.raises(ValueError, match="selected=SUGAMO_SHINKIN, detected=JAPAN_POST_BANK"):
        service.run_extraction_from_csv(db, b"wrong", "SUGAMO_SHINKIN", "wrong.csv", "tester")
    assert db.execute(text(f"SELECT COUNT(*) FROM {service.BATCH_TABLE}")).scalar_one() == 0


def test_page_uses_bank_and_original_csv_without_business_month():
    page = (ROOT / "src/web/static/bank_remitter_candidate_center.html").read_text(encoding="utf-8")
    route = (ROOT / "src/api/routes/tlc_bank_remitter_candidate.py").read_text(encoding="utf-8")
    assert "TLC_BANK_REMITTER_CANDIDATE_FROM_CSV_R1" in page
    assert 'id="selectedBank"' in page
    assert 'id="sourceFile"' in page
    assert "selected_bank_code" in page
    assert "businessMonth" not in page
    assert "不读取、也不写入正式银行流水" in page
    assert "run_extraction_from_csv" in route
