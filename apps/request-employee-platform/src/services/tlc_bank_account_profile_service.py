from __future__ import annotations
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.services.tlc_code_master_service import ensure_tlc_code_tables
TABLE_NAME="tlc_bank_account_profile"
def ensure_table(db:Session):
 ensure_tlc_code_tables(db)
 db.execute(text(f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME}(id VARCHAR(64) PRIMARY KEY,bank_code VARCHAR(128) NOT NULL,branch_code VARCHAR(128) NOT NULL DEFAULT '',branch_name VARCHAR(255) NOT NULL DEFAULT '',account_type VARCHAR(128) NOT NULL DEFAULT '',account_number VARCHAR(255) NOT NULL,account_holder VARCHAR(500) NOT NULL DEFAULT '',adapter_code VARCHAR(128) NOT NULL DEFAULT '',file_encoding VARCHAR(64) NOT NULL DEFAULT 'cp932',active INTEGER NOT NULL DEFAULT 1,note TEXT NOT NULL DEFAULT '',created_at VARCHAR(64) NOT NULL,updated_at VARCHAR(64) NOT NULL,UNIQUE(bank_code,account_number))"""));db.commit()
def seed_banks(db:Session):
 ensure_tlc_code_tables(db);now=datetime.now(timezone.utc).isoformat()
 for code,zh,ja,en,sort in [('SUGAMO_SHINKIN','巣鴨信用金庫','巣鴨信用金庫','Sugamo Shinkin Bank',10),('JAPAN_POST_BANK','邮储银行','ゆうちょう銀行','Japan Post Bank',20)]:
  if db.execute(text("SELECT id FROM tlc_code_value WHERE category_code='BANK' AND code=:c"),{'c':code}).first():continue
  db.execute(text("""INSERT INTO tlc_code_value(id,category_code,code,name_zh,name_ja,name_en,sort_order,active,extra_json,created_at,updated_at) VALUES(:id,'BANK',:code,:zh,:ja,:en,:sort,1,'{}',:now,:now)"""),{'id':uuid4().hex,'code':code,'zh':zh,'ja':ja,'en':en,'sort':sort,'now':now})
 db.commit()
def row(r):
 d=dict(r._mapping);d['active']=bool(d['active']);return d
def list_profiles(db:Session,bank_code='',account_number=''):
 ensure_table(db);clauses=[];p={}
 if bank_code:clauses.append('bank_code=:bank');p['bank']=bank_code
 if account_number:clauses.append('account_number LIKE :acct');p['acct']=f'%{account_number}%'
 w='WHERE '+' AND '.join(clauses) if clauses else ''
 return [row(r) for r in db.execute(text(f'SELECT * FROM {TABLE_NAME} {w} ORDER BY bank_code,branch_code,account_number'),p).all()]
def save_profile(db:Session,payload):
 ensure_table(db);seed_banks(db)
 bank=str(payload.get('bank_code','')).strip().upper();acct=str(payload.get('account_number','')).strip();rid=str(payload.get('id','')).strip()
 if not bank or not acct:raise ValueError('bank_code and account_number are required')
 if not db.execute(text("SELECT id FROM tlc_code_value WHERE category_code='BANK' AND code=:c"),{'c':bank}).first():raise ValueError('bank_code does not exist in TLC Code Master')
 dup=db.execute(text(f'SELECT id FROM {TABLE_NAME} WHERE bank_code=:b AND account_number=:a'),{'b':bank,'a':acct}).first();now=datetime.now(timezone.utc).isoformat()
 p={'bank_code':bank,'branch_code':str(payload.get('branch_code','')),'branch_name':str(payload.get('branch_name','')),'account_type':str(payload.get('account_type','')),'account_number':acct,'account_holder':str(payload.get('account_holder','')),'adapter_code':str(payload.get('adapter_code','')),'file_encoding':str(payload.get('file_encoding','cp932') or 'cp932'),'active':1 if payload.get('active',True) else 0,'note':str(payload.get('note','')),'updated_at':now}
 if rid:
  if dup and dup._mapping['id']!=rid:raise ValueError('bank account already exists')
  p['id']=rid;res=db.execute(text(f"""UPDATE {TABLE_NAME} SET bank_code=:bank_code,branch_code=:branch_code,branch_name=:branch_name,account_type=:account_type,account_number=:account_number,account_holder=:account_holder,adapter_code=:adapter_code,file_encoding=:file_encoding,active=:active,note=:note,updated_at=:updated_at WHERE id=:id"""),p)
  if res.rowcount==0:raise LookupError('Bank account profile not found')
 else:
  if dup:raise ValueError('bank account already exists')
  rid=uuid4().hex;p.update({'id':rid,'created_at':now});db.execute(text(f"""INSERT INTO {TABLE_NAME}(id,bank_code,branch_code,branch_name,account_type,account_number,account_holder,adapter_code,file_encoding,active,note,created_at,updated_at) VALUES(:id,:bank_code,:branch_code,:branch_name,:account_type,:account_number,:account_holder,:adapter_code,:file_encoding,:active,:note,:created_at,:updated_at)"""),p)
 db.commit();return row(db.execute(text(f'SELECT * FROM {TABLE_NAME} WHERE id=:id'),{'id':rid}).first())
