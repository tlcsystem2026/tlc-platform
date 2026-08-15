from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_customer_master_service import save_customer
from src.services.tlc_customer_name_identity_service import list_names


def _db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'identity-sync.db'}")
    return sessionmaker(bind=engine)()


def test_all_customer_master_names_are_synchronized(tmp_path):
    db = _db(tmp_path)
    customer = save_customer(db, {
        "customer_id": "C-100",
        "formal_name": "Formal Name",
        "short_name": "Short Name",
        "delivery_name_1": "Delivery One",
        "delivery_name_2": "Delivery Two",
        "alias_1": "Old Alias",
    })
    rows = list_names(db, customer_id="C-100")
    assert {(row["name_value"], row["name_type"]) for row in rows} >= {
        ("Formal Name", "FORMAL"),
        ("Short Name", "SHORT_NAME"),
        ("Delivery One", "DELIVERY_NAME"),
        ("Delivery Two", "DELIVERY_NAME"),
        ("Old Alias", "HISTORICAL"),
    }

    updated = dict(customer)
    updated.update({"customer_id": "C-101", "alias_1": "New Alias", "updated_by": "tester"})
    save_customer(db, updated)
    active = list_names(db, customer_id="C-101")
    assert all(row["customer_id"] == "C-101" for row in active)
    assert any(row["name_value"] == "New Alias" for row in active)
    assert not any(row["name_value"] == "Old Alias" for row in active)


def test_inactive_customer_retires_all_identities(tmp_path):
    db = _db(tmp_path)
    customer = save_customer(db, {
        "customer_id": "C-200",
        "formal_name": "Inactive Customer",
        "alias_1": "Inactive Alias",
    })
    changed = dict(customer)
    changed["active"] = False
    save_customer(db, changed)
    assert list_names(db, customer_id="C-200") == []
    rows = db.execute(text("SELECT active FROM tlc_customer_name_identity WHERE customer_id='C-200'"))
    assert rows.all() and all(int(row[0]) == 0 for row in rows)
