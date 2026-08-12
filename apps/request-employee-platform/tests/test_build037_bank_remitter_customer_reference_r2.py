from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.services.tlc_customer_master_service import list_customers, save_customer


ROOT = Path(__file__).parents[1]


def test_customer_reference_search_is_partial_and_all_field(tmp_path):
    db = sessionmaker(bind=create_engine(f"sqlite:///{tmp_path / 'reference.db'}"))()
    save_customer(db, {
        "customer_id": "REF-001", "formal_name": "株式会社藤原商店",
        "short_name": "ふじ店", "delivery_name_1": "東京配送センター",
        "alias_3": "FUJI REMITTER", "active": False,
    })
    assert list_customers(db, formal_name="藤原")[0]["customer_id"] == "REF-001"
    assert list_customers(db, query="東京配送")[0]["customer_id"] == "REF-001"
    assert list_customers(db, query="FUJI REMIT")[0]["customer_id"] == "REF-001"
    assert list_customers(db, query="ふじ店")[0]["customer_id"] == "REF-001"


def test_reference_page_uses_full_and_field_partial_search():
    page = (ROOT / "src/web/static/bank_remitter_candidate_center.html").read_text(encoding="utf-8")
    assert "TLC_BANK_REMITTER_CUSTOMER_REFERENCE_R2" in page
    assert "全字段综合检索" in page
    assert 'id="customerFieldQuery"' in page
    assert 'id="customerFieldValue"' in page
    assert 'include_inactive:"true"' in page
    assert 'q.set(field,fieldValue)' in page
    assert "全部条件均为部分匹配" in page
