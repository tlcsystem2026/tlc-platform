from __future__ import annotations
import json
from datetime import datetime,timezone
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
CATEGORY_TABLE="tlc_code_category"
VALUE_TABLE="tlc_code_value"
DEFAULT_CATEGORIES=[("BANK","银行","銀行","Bank"),("CUSTOMER_STATUS","客户状态","顧客状態","Customer Status"),("REVIEW_STATUS","审核状态","審査状態","Review Status"),("TRANSACTION_DIRECTION","交易方向","取引方向","Transaction Direction"),("RECONCILIATION_STATUS","对账状态","照合状態","Reconciliation Status"),("IMPORT_STATUS","导入状态","取込状態","Import Status"),("CURRENCY","币种","通貨","Currency")]
def ensure_tlc_code_tables(db:Session)->None:
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {CATEGORY_TABLE}(id VARCHAR(64) PRIMARY KEY,category_code VARCHAR(128) NOT NULL UNIQUE,name_zh VARCHAR(255) NOT NULL DEFAULT '',name_ja VARCHAR(255) NOT NULL DEFAULT '',name_en VARCHAR(255) NOT NULL DEFAULT '',description TEXT NOT NULL DEFAULT '',sort_order INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1,created_at VARCHAR(64) NOT NULL,updated_at VARCHAR(64) NOT NULL)"""))
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {VALUE_TABLE}(id VARCHAR(64) PRIMARY KEY,category_code VARCHAR(128) NOT NULL,code VARCHAR(128) NOT NULL,name_zh VARCHAR(255) NOT NULL DEFAULT '',name_ja VARCHAR(255) NOT NULL DEFAULT '',name_en VARCHAR(255) NOT NULL DEFAULT '',sort_order INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1,extra_json TEXT NOT NULL DEFAULT '{{}}',created_at VARCHAR(64) NOT NULL,updated_at VARCHAR(64) NOT NULL,UNIQUE(category_code,code))"""))
    db.commit(); seed_default_categories(db)
def seed_default_categories(db:Session)->None:
    now=datetime.now(timezone.utc).isoformat()
    for i,(code,zh,ja,en) in enumerate(DEFAULT_CATEGORIES,1):
        if db.execute(text(f"SELECT id FROM {CATEGORY_TABLE} WHERE category_code=:c"),{"c":code}).first(): continue
        db.execute(text(f"INSERT INTO {CATEGORY_TABLE}(id,category_code,name_zh,name_ja,name_en,description,sort_order,active,created_at,updated_at) VALUES(:id,:c,:zh,:ja,:en,'',:s,1,:now,:now)"),{"id":uuid4().hex,"c":code,"zh":zh,"ja":ja,"en":en,"s":i*10,"now":now})
    db.commit()
def _row(r:Any)->dict[str,Any]:
    d=dict(r._mapping if hasattr(r,'_mapping') else r)
    if 'active' in d:d['active']=bool(d['active'])
    if 'extra_json' in d:
        try:d['extra_json']=json.loads(d['extra_json'] or '{}')
        except Exception:d['extra_json']={}
    return d
def list_categories(db:Session,include_inactive:bool=True):
    ensure_tlc_code_tables(db); where='' if include_inactive else 'WHERE active=1'
    return [_row(r) for r in db.execute(text(f"SELECT * FROM {CATEGORY_TABLE} {where} ORDER BY sort_order,category_code")).all()]
def save_category(db:Session,p:dict[str,Any]):
    ensure_tlc_code_tables(db); code=str(p.get('category_code','')).strip().upper()
    if not code: raise ValueError('category_code is required')
    now=datetime.now(timezone.utc).isoformat(); rid=str(p.get('id','')).strip()
    dup=db.execute(text(f"SELECT id FROM {CATEGORY_TABLE} WHERE category_code=:c"),{'c':code}).first()
    vals={'id':rid,'c':code,'zh':str(p.get('name_zh','')),'ja':str(p.get('name_ja','')),'en':str(p.get('name_en','')),'d':str(p.get('description','')),'s':int(p.get('sort_order',0) or 0),'a':1 if p.get('active',True) else 0,'now':now}
    if rid:
        if dup and dup._mapping['id']!=rid: raise ValueError('category_code already exists')
        u=db.execute(text(f"UPDATE {CATEGORY_TABLE} SET category_code=:c,name_zh=:zh,name_ja=:ja,name_en=:en,description=:d,sort_order=:s,active=:a,updated_at=:now WHERE id=:id"),vals)
        if u.rowcount==0: raise LookupError('Category not found')
    else:
        if dup: raise ValueError('category_code already exists')
        vals['id']=rid=uuid4().hex
        db.execute(text(f"INSERT INTO {CATEGORY_TABLE}(id,category_code,name_zh,name_ja,name_en,description,sort_order,active,created_at,updated_at) VALUES(:id,:c,:zh,:ja,:en,:d,:s,:a,:now,:now)"),vals)
    db.commit(); return _row(db.execute(text(f"SELECT * FROM {CATEGORY_TABLE} WHERE id=:id"),{'id':rid}).first())
def list_values(db:Session,category_code:str):
    ensure_tlc_code_tables(db)
    return [_row(r) for r in db.execute(text(f"SELECT * FROM {VALUE_TABLE} WHERE category_code=:c ORDER BY sort_order,code"),{'c':category_code}).all()]
def save_value(db:Session,p:dict[str,Any]):
    ensure_tlc_code_tables(db); cat=str(p.get('category_code','')).strip().upper(); code=str(p.get('code','')).strip().upper()
    if not cat or not code: raise ValueError('category_code and code are required')
    if not db.execute(text(f"SELECT id FROM {CATEGORY_TABLE} WHERE category_code=:c"),{'c':cat}).first(): raise ValueError('category_code does not exist')
    extra=p.get('extra_json',{}) or {}
    if not isinstance(extra,dict): raise ValueError('extra_json must be an object')
    now=datetime.now(timezone.utc).isoformat(); rid=str(p.get('id','')).strip()
    dup=db.execute(text(f"SELECT id FROM {VALUE_TABLE} WHERE category_code=:cat AND code=:code"),{'cat':cat,'code':code}).first()
    vals={'id':rid,'cat':cat,'code':code,'zh':str(p.get('name_zh','')),'ja':str(p.get('name_ja','')),'en':str(p.get('name_en','')),'s':int(p.get('sort_order',0) or 0),'a':1 if p.get('active',True) else 0,'x':json.dumps(extra,ensure_ascii=False),'now':now}
    if rid:
        if dup and dup._mapping['id']!=rid: raise ValueError('code already exists in category')
        u=db.execute(text(f"UPDATE {VALUE_TABLE} SET category_code=:cat,code=:code,name_zh=:zh,name_ja=:ja,name_en=:en,sort_order=:s,active=:a,extra_json=:x,updated_at=:now WHERE id=:id"),vals)
        if u.rowcount==0: raise LookupError('Code value not found')
    else:
        if dup: raise ValueError('code already exists in category')
        vals['id']=rid=uuid4().hex
        db.execute(text(f"INSERT INTO {VALUE_TABLE}(id,category_code,code,name_zh,name_ja,name_en,sort_order,active,extra_json,created_at,updated_at) VALUES(:id,:cat,:code,:zh,:ja,:en,:s,:a,:x,:now,:now)"),vals)
    db.commit(); return _row(db.execute(text(f"SELECT * FROM {VALUE_TABLE} WHERE id=:id"),{'id':rid}).first())
