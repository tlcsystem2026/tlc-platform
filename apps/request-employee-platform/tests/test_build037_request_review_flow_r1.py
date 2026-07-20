from pathlib import Path
from sqlalchemy import create_engine,text
from sqlalchemy.orm import sessionmaker
from src.services.request_review_service import ensure_review_tables,update_review
from src.services.request_pending_review_resolution_service import resolve_pending_review

def test_page_names():
 root=Path(__file__).parents[1]
 assert '请求书导入Batch与文件核对' in (root/'src/web/static/request_review_center.html').read_text(encoding='utf-8')
 assert '请求书业务审核' in (root/'src/web/static/request_review_workbench.html').read_text(encoding='utf-8')

def test_file_review_to_business_review_to_sales(tmp_path):
 engine=create_engine(f"sqlite:///{(tmp_path/'f.sqlite3').as_posix()}");db=sessionmaker(bind=engine)()
 try:
  db.execute(text('CREATE TABLE tlc_request_batch_compare_item(id TEXT PRIMARY KEY,batch_id TEXT,business_month TEXT,pair_key TEXT,pdf_file_name TEXT,excel_file_name TEXT,final_pdf_path TEXT,final_excel_path TEXT,pdf_total_amount TEXT,excel_total_amount TEXT,raw_customer_name TEXT,system_customer_code TEXT,system_customer_name TEXT,customer_match_status TEXT,compare_status TEXT,exception_details TEXT,pdf_sha256 TEXT,excel_sha256 TEXT,pdf_raw_text TEXT,excel_raw_json TEXT,created_at TEXT)'))
  db.execute(text('CREATE TABLE tlc_request_review_queue(id TEXT PRIMARY KEY,batch_id TEXT,item_id TEXT UNIQUE,business_month TEXT,pair_key TEXT,review_status TEXT,compare_status TEXT,raw_customer_name TEXT,system_customer_code TEXT,system_customer_name TEXT,exception_codes TEXT,created_at TEXT)'))
  db.execute(text("INSERT INTO tlc_request_batch_compare_item VALUES('i1','b1','202601','REQ-1','a.pdf','a.xlsx','a.pdf','a.xlsx','100','100','C','C1','C','MATCHED','MATCHED','','p','x','pdf','{}','now')"))
  db.execute(text("INSERT INTO tlc_request_review_queue VALUES('r1','b1','i1','202601','REQ-1','WAIT_REVIEW','MATCHED','C','C1','C','','now')"));db.commit();ensure_review_tables(db)
  update_review(db,'r1','REVIEWED_OK','file-user','',False)
  pending=db.execute(text("SELECT id,status FROM request_pending_review WHERE file_review_id='r1'")).first();assert pending and pending._mapping['status']=='PENDING_REVIEW'
  result=resolve_pending_review(db,pending._mapping['id'],action='APPROVE',reviewed_by='business-user',note='ok')
  assert result['new_status']=='APPROVED' and result['sales_ledger']['status']=='posted'
  assert db.execute(text('SELECT COUNT(*) FROM formal_sales_request_ledger')).scalar_one()==1
 finally:db.close();engine.dispose()
