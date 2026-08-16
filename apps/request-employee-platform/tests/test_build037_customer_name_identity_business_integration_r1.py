from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.services.customer_bank_name_matching_service import match_customer_by_bank_counterparty
from src.services.formal_sales_ledger_service import list_sales_ledger
from src.services.request_batch_compare_import_service import _match_customer
from src.services.request_pending_review_service import list_pending_reviews
from src.services.tlc_customer_master_service import save_customer
from src.services.tlc_customer_name_identity_service import register_name


ROOT = Path(__file__).parents[1]
BUSINESS_SERVICES = (
    "formal_sales_ledger_service.py",
    "request_pending_review_service.py",
    "request_batch_compare_import_service.py",
    "tlc_customer_candidate_service.py",
    "tlc_customer_name_matching_service.py",
    "customer_bank_name_matching_service.py",
    "tlc_bank_remitter_candidate_service.py",
)


def test_request_and_bank_names_resolve_to_same_customer(tmp_path):
    db = sessionmaker(bind=create_engine(f"sqlite:///{tmp_path/'integration.db'}"))()
    customer = save_customer(db, {"customer_id": "C-ONE", "formal_name": "Canonical Customer"})
    register_name(db, customer_record_id=customer["id"], customer_id="C-ONE",
                  name_value="中文客户名称", name_type="REQUEST_NAME", language_code="zh")
    register_name(db, customer_record_id=customer["id"], customer_id="C-ONE",
                  name_value="ニホンゴフリコミ", name_type="BANK_REMITTER", language_code="ja")
    request = _match_customer(db, "中文客户名称")
    bank = match_customer_by_bank_counterparty(db, "ニホンゴフリコミ")
    assert request[0] == bank.customer_id == "C-ONE"
    assert request[2] == bank.status == "MATCHED"


def test_business_services_do_not_read_retired_name_columns():
    for filename in BUSINESS_SERVICES:
        source = (ROOT / "src/services" / filename).read_text(encoding="utf-8")
        for number in range(1, 6):
            assert "c." + ("a" + "lias") + f"_{number}" not in source, filename
            assert 'customer.get("' + ("a" + "lias") + f'_{number}"' not in source, filename


def test_business_queries_use_name_identity_table():
    for filename in (
        "formal_sales_ledger_service.py",
        "request_pending_review_service.py",
        "request_batch_compare_import_service.py",
        "customer_bank_name_matching_service.py",
    ):
        source = (ROOT / "src/services" / filename).read_text(encoding="utf-8")
        assert "tlc_customer_name_identity" in source or "match_name" in source, filename


def test_review_and_sales_name_filters_execute_with_identity_table(tmp_path):
    db = sessionmaker(bind=create_engine(f"sqlite:///{tmp_path/'queries.db'}"))()
    customer = save_customer(db, {"customer_id": "C-Q", "formal_name": "Query Customer"})
    register_name(db, customer_record_id=customer["id"], customer_id="C-Q",
                  name_value="检索名称", name_type="REQUEST_NAME")
    assert list_pending_reviews(db, customer_name="检索名称") == []
    assert list_sales_ledger(db, customer_name="检索名称") == []
