from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.multi_bank_csv_import_service import ensure_bank_transaction_table
from src.services.tlc_bank_remitter_candidate_service import list_candidates, resolve_candidate, run_extraction
from src.services.tlc_customer_master_service import ensure_customer_master_table, save_customer


ROOT = Path(__file__).parents[1]


def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'remitter.db'}")
    return sessionmaker(bind=engine)()


def test_extracts_credit_remitters_by_month_and_adds_alias(tmp_path):
    db = session(tmp_path)
    ensure_bank_transaction_table(db)
    ensure_customer_master_table(db)
    customer = save_customer(db, {"customer_id": "CUST-001", "formal_name": "Example Customer"})
    db.execute(text("""INSERT INTO bank_transaction_import(id,bank_code,bank_name,account_number,transaction_id,
      transaction_date,deposit_amount,withdrawal_amount,amount,direction,counterparty,description,balance,
      source_file,import_batch_id,imported_at) VALUES
      ('t1','SUGAMO_SHINKIN','Sugamo','1','x1','2026-08-01','100','','100','CREDIT','EXAMPLE PAY','transfer','','a.csv','b1','now'),
      ('t2','JAPAN_POST_BANK','Japan Post','2','x2','2026-08-02','200','','200','CREDIT','EXAMPLE PAY','transfer','','b.csv','b2','now'),
      ('t3','SUGAMO_SHINKIN','Sugamo','1','x3','2026-08-03','','50','50','DEBIT','IGNORE ME','debit','','c.csv','b3','now')"""))
    db.commit()
    batch = run_extraction(db, "202608", "tester")
    assert batch["transaction_count"] == 2
    rows = list_candidates(db, batch_id=batch["id"])
    assert len(rows) == 1
    assert rows[0]["transaction_count"] == 2
    assert rows[0]["total_amount"] == "300"
    assert rows[0]["bank_codes"] == "JAPAN_POST_BANK,SUGAMO_SHINKIN"
    result = resolve_candidate(db, rows[0]["id"], "ADD_ALIAS", "tester", customer["customer_id"])
    assert result["review_status"] == "RESOLVED"
    alias = db.execute(text("SELECT alias_1 FROM tlc_customer_master WHERE id=:id"), {"id": customer["id"]}).scalar_one()
    assert alias == "EXAMPLE PAY"


def test_page_routes_permissions_and_dashboard_contracts():
    main = (ROOT / "src/main.py").read_text(encoding="utf-8")
    page = (ROOT / "src/web/static/bank_remitter_candidate_center.html").read_text(encoding="utf-8")
    dashboard = (ROOT / "src/web/static/dashboard.html").read_text(encoding="utf-8")
    permissions = (ROOT / "src/services/tlc_api_permission_service.py").read_text(encoding="utf-8")
    assert "TLC_BANK_REMITTER_CANDIDATE_BATCH_R1" in main
    assert "/api/bank-remitter-candidates/batches" in page
    assert "/bank-remitter-candidate-center" in dashboard
    assert dashboard.count('/bank-remitter-candidate-center') == 1
    assert dashboard.index('/tlc-bank-account-master') < dashboard.index('/bank-remitter-candidate-center')
    assert dashboard.index('/bank-remitter-candidate-center') < dashboard.index('② 请求书与正式销售')
    assert "BANK_CUSTOMER_MATCHING" in permissions
