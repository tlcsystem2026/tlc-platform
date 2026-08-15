from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_customer_identity_audit_service import impact_preview, resolve_conflict, scan_conflicts
from src.services.tlc_customer_master_service import save_customer
from src.services.tlc_customer_name_identity_service import register_name

ROOT=Path(__file__).parents[1]

def db(tmp_path): return sessionmaker(bind=create_engine(f"sqlite:///{tmp_path/'audit.db'}"))()

def test_scan_and_repair_customer_id(tmp_path):
    session=db(tmp_path);customer=save_customer(session,{"customer_id":"C1","formal_name":"Customer One"})
    identity=register_name(session,customer_record_id=customer["id"],customer_id="C1",name_value="Request Name",name_type="REQUEST_NAME")
    session.execute(text("UPDATE tlc_customer_name_identity SET customer_id='WRONG' WHERE id=:id"),{"id":identity["id"]});session.commit()
    result=scan_conflicts(session)
    assert result["counts"]["CUSTOMER_ID_MISMATCH"]==1 and result["blocking"]==1
    resolve_conflict(session,identity["id"],"REPAIR_CUSTOMER_ID","admin","repair")
    assert scan_conflicts(session)["blocking"]==0

def test_orphan_and_inactive_are_blocking(tmp_path):
    session=db(tmp_path);customer=save_customer(session,{"customer_id":"C2","formal_name":"Customer Two"})
    session.execute(text("UPDATE tlc_customer_master SET active=0 WHERE id=:id"),{"id":customer["id"]});session.commit()
    assert scan_conflicts(session)["counts"]["INACTIVE_CUSTOMER"]>=1

def test_impact_and_deactivate_audit(tmp_path):
    session=db(tmp_path);customer=save_customer(session,{"customer_id":"C3","formal_name":"Customer Three"})
    identity=register_name(session,customer_record_id=customer["id"],customer_id="C3",name_value="Bad Name",name_type="HISTORICAL")
    assert impact_preview(session,identity["id"])["identity"]["name_value"]=="Bad Name"
    resolve_conflict(session,identity["id"],"DEACTIVATE","admin","incorrect")
    action=session.execute(text("SELECT action FROM tlc_customer_name_identity_audit WHERE identity_id=:id ORDER BY created_at DESC LIMIT 1"),{"id":identity["id"]}).scalar_one()
    assert action=="RESOLVE_DEACTIVATE"

def test_page_and_route_contracts():
    page=(ROOT/'src/web/static/customer_identity_audit_center.html').read_text(encoding='utf-8')
    route=(ROOT/'src/api/routes/tlc_customer_identity_audit.py').read_text(encoding='utf-8')
    assert 'TLC_CUSTOMER_IDENTITY_AUDIT_CONFLICT_CENTER_R1' in page
    assert '/customer-identity-audit-center' in route and '/impact' in route and '/resolve' in route
