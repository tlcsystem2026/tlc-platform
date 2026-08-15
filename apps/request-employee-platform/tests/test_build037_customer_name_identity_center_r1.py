from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.services.tlc_customer_master_service import save_customer
from src.services.tlc_customer_name_identity_service import list_names, register_name, deactivate_name

ROOT=Path(__file__).parents[1]
def test_identity_maintenance(tmp_path):
 db=sessionmaker(bind=create_engine(f"sqlite:///{tmp_path/'x.db'}"))();c=save_customer(db,{"customer_id":"C1","formal_name":"日本名株式会社"});x=register_name(db,customer_record_id=c['id'],customer_id='C1',name_value='中文名称有限公司',name_type='REQUEST_NAME',language_code='zh',actor='u');assert list_names(db,query='中文')[0]['customer_id']=='C1';deactivate_name(db,x['id'],'u','wrong alias');assert list_names(db,include_inactive=True)[-1]['active']==0
def test_registration_rejects_mismatched_customer_reference(tmp_path):
 db=sessionmaker(bind=create_engine(f"sqlite:///{tmp_path/'m.db'}"))();a=save_customer(db,{"customer_id":"A","formal_name":"甲株式会社"});save_customer(db,{"customer_id":"B","formal_name":"乙株式会社"})
 try:register_name(db,customer_record_id=a['id'],customer_id='B',name_value='错误名称',name_type='REQUEST_NAME')
 except ValueError as exc:assert 'do not identify the same customer' in str(exc)
 else:raise AssertionError('mismatched customer reference was accepted')
def test_page_and_route_contracts():
 page=(ROOT/'src/web/static/customer_name_identity_center.html').read_text(encoding='utf-8');route=(ROOT/'src/api/routes/tlc_customer_name_identity.py').read_text(encoding='utf-8');assert '/customer-name-identity-center' in route;assert 'REQUEST_NAME' in page and 'BANK_REMITTER' in page and '/dashboard' in page;assert 'openCustomerReference' in page and '/api/tlc-customers?' in page and 'sortBy(' in page and 'pageTo(' in page
