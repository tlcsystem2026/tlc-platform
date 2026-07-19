from pathlib import Path
from sqlalchemy import create_engine,text
from sqlalchemy.orm import sessionmaker
from src.services.tlc_customer_master_service import EXTRA_COLUMNS,ensure_customer_master_table,import_todokedl_csv,list_customers

def test_customer_todokedl_full_layout(tmp_path):
 e=create_engine(f"sqlite:///{(tmp_path/'c.db').as_posix()}");db=sessionmaker(bind=e)()
 try:
  ensure_customer_master_table(db);cols={r._mapping['name'] for r in db.execute(text('PRAGMA table_info(tlc_customer_master)')).all()};assert set(EXTRA_COLUMNS)<=cols
  raw=('お届け先コード,郵便番号,お届け先名称１,お届け先名称２,お届け先住所１,お届け先住所２,お届け先電話番号,カナ名称,お届け先Eメールアドレス,JIS市町村コード,出荷通知メール希望区分,荷送人コード\nC1,1000001,配送名,担当,住所1,住所2,0312345678,ハイソウ,a@example.com,13101,1,S1\n').encode('cp932')
  assert import_todokedl_csv(db,raw)['inserted']==1;r=list_customers(db,customer_id='C1')[0];assert r['formal_name']=='' and r['katakana_name']=='' and r['delivery_name_1']=='配送名' and r['email_address']=='a@example.com'
 finally:db.close();e.dispose()
 p=(Path(__file__).parents[1]/'src/web/static/tlc_customer_master.html').read_text(encoding='utf-8')
 for x in ['BUILD037_STEP05_CUSTOMER_PAGE','客户维护','CSV 导入','CSV 导出','别名5','/api/tlc-customers/import','/api/tlc-customers/export.csv','katakana_name_short','source_updated_at']:assert x in p
 assert p.index('单个客户维护')<p.index('检索条件')<p.index('客户一览')
