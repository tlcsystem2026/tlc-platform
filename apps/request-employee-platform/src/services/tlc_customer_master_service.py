from __future__ import annotations
import csv, io, re, unicodedata
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.services.tlc_code_master_service import ensure_tlc_code_tables

TABLE_NAME="tlc_customer_master"
EXTRA_COLUMNS={
"katakana_name_short":"VARCHAR(500) NOT NULL DEFAULT ''",
"delivery_name_1":"VARCHAR(500) NOT NULL DEFAULT ''","delivery_name_2":"VARCHAR(500) NOT NULL DEFAULT ''",
"postal_code":"VARCHAR(32) NOT NULL DEFAULT ''","address_1":"VARCHAR(1000) NOT NULL DEFAULT ''","address_2":"VARCHAR(1000) NOT NULL DEFAULT ''",
"phone_number":"VARCHAR(128) NOT NULL DEFAULT ''","email_address":"VARCHAR(500) NOT NULL DEFAULT ''",
"jis_municipality_code":"VARCHAR(64) NOT NULL DEFAULT ''","shipping_notice_email_flag":"VARCHAR(64) NOT NULL DEFAULT ''",
"shipper_code":"VARCHAR(128) NOT NULL DEFAULT ''","source_system":"VARCHAR(128) NOT NULL DEFAULT ''","source_updated_at":"VARCHAR(64) NOT NULL DEFAULT ''"}
TODOKEDL={"お届け先コード":"customer_id","郵便番号":"postal_code","お届け先名称１":"delivery_name_1","お届け先名称２":"delivery_name_2","お届け先住所１":"address_1","お届け先住所２":"address_2","お届け先電話番号":"phone_number","カナ名称":"katakana_name_short","お届け先Eメールアドレス":"email_address","JIS市町村コード":"jis_municipality_code","出荷通知メール希望区分":"shipping_notice_email_flag","荷送人コード":"shipper_code"}
ALL_FIELDS=["id","customer_id","formal_name","hiragana_name","katakana_name","katakana_name_short","short_name","delivery_name_1","delivery_name_2","postal_code","address_1","address_2","phone_number","email_address","jis_municipality_code","shipping_notice_email_flag","shipper_code","alias_1","alias_2","alias_3","alias_4","alias_5","normalized_formal_name","status_code","active","note","source_system","source_updated_at","created_at","updated_at"]

def normalize_customer_name(v:str)->str:
    s=unicodedata.normalize("NFKC",str(v or "")).casefold();s=re.sub(r"\s+","",s)
    for t in ("株式会社","有限会社","合同会社","（株）","(株)","㈱"):s=s.replace(t.casefold(),"")
    return s.strip()

def ensure_customer_master_table(db:Session)->None:
    ensure_tlc_code_tables(db)
    db.execute(text(f'''CREATE TABLE IF NOT EXISTS {TABLE_NAME}(
      id VARCHAR(64) PRIMARY KEY,customer_id VARCHAR(128) NOT NULL UNIQUE,formal_name VARCHAR(500) NOT NULL DEFAULT '',
      hiragana_name VARCHAR(500) NOT NULL DEFAULT '',katakana_name VARCHAR(500) NOT NULL DEFAULT '',short_name VARCHAR(500) NOT NULL DEFAULT '',
      alias_1 VARCHAR(500) NOT NULL DEFAULT '',alias_2 VARCHAR(500) NOT NULL DEFAULT '',alias_3 VARCHAR(500) NOT NULL DEFAULT '',alias_4 VARCHAR(500) NOT NULL DEFAULT '',alias_5 VARCHAR(500) NOT NULL DEFAULT '',
      normalized_formal_name VARCHAR(500) NOT NULL DEFAULT '',status_code VARCHAR(128) NOT NULL DEFAULT 'ACTIVE',active INTEGER NOT NULL DEFAULT 1,
      note TEXT NOT NULL DEFAULT '',created_at VARCHAR(64) NOT NULL,updated_at VARCHAR(64) NOT NULL)'''))
    existing={r._mapping['name'] for r in db.execute(text(f"PRAGMA table_info({TABLE_NAME})")).all()}
    for c,d in EXTRA_COLUMNS.items():
        if c not in existing:db.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {c} {d}"))
    db.commit()

def _row(r:Any)->dict[str,Any]:
    x=dict(r._mapping if hasattr(r,'_mapping') else r);x['active']=bool(x.get('active',0));return x

def list_customers(db:Session,query:str='',customer_id:str='',formal_name:str='',katakana_name:str='',katakana_name_short:str='',delivery_name_1:str='',delivery_name_2:str='',phone_number:str='',postal_code:str='',address:str='',status_code:str='',source_system:str='',include_inactive:bool=True,limit:int=500)->list[dict[str,Any]]:
    ensure_customer_master_table(db);clauses=[];p={'limit':min(max(int(limit),1),2000)}
    if query:
        clauses.append("("+" OR ".join(f"{c} LIKE :q" for c in ['customer_id','formal_name','hiragana_name','katakana_name','katakana_name_short','short_name','delivery_name_1','delivery_name_2','postal_code','address_1','address_2','phone_number','email_address','jis_municipality_code','shipper_code','alias_1','alias_2','alias_3','alias_4','alias_5'])+")");p['q']=f'%{query}%'
    for c,v in {'customer_id':customer_id,'formal_name':formal_name,'katakana_name':katakana_name,'katakana_name_short':katakana_name_short,'delivery_name_1':delivery_name_1,'delivery_name_2':delivery_name_2,'phone_number':phone_number,'postal_code':postal_code,'source_system':source_system}.items():
        if v:clauses.append(f"{c} LIKE :{c}");p[c]=f'%{v}%'
    if address:clauses.append('(address_1 LIKE :address OR address_2 LIKE :address)');p['address']=f'%{address}%'
    if status_code:clauses.append('status_code=:status_code');p['status_code']=status_code
    if not include_inactive:clauses.append('active=1')
    where='WHERE '+' AND '.join(clauses) if clauses else ''
    return [_row(r) for r in db.execute(text(f"SELECT * FROM {TABLE_NAME} {where} ORDER BY customer_id LIMIT :limit"),p).all()]

def get_customer(db:Session,record_id:str):
    ensure_customer_master_table(db);r=db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id"),{'id':record_id}).first();return _row(r) if r else None

def save_customer(db:Session,payload:dict[str,Any]):
    ensure_customer_master_table(db);cid=str(payload.get('customer_id','')).strip();formal=str(payload.get('formal_name','')).strip()
    if not cid:raise ValueError('customer_id is required')
    if not formal:raise ValueError('formal_name is required for manual maintenance')
    rid=str(payload.get('id','')).strip();now=datetime.now(timezone.utc).isoformat()
    cols=['customer_id','formal_name','hiragana_name','katakana_name','katakana_name_short','short_name','delivery_name_1','delivery_name_2','postal_code','address_1','address_2','phone_number','email_address','jis_municipality_code','shipping_notice_email_flag','shipper_code','alias_1','alias_2','alias_3','alias_4','alias_5','status_code','note','source_system','source_updated_at']
    p={c:str(payload.get(c,'') or '').strip() for c in cols};p.update({'customer_id':cid,'formal_name':formal,'normalized_formal_name':normalize_customer_name(formal),'active':1 if payload.get('active',True) else 0,'updated_at':now})
    allcols=cols+['normalized_formal_name','active','updated_at']
    if rid:
        p['id']=rid;r=db.execute(text(f"UPDATE {TABLE_NAME} SET "+','.join(f'{c}=:{c}' for c in allcols)+" WHERE id=:id"),p)
        if r.rowcount==0:raise LookupError('Customer not found')
    else:
        rid=uuid4().hex;p.update({'id':rid,'created_at':now});ins=['id']+allcols+['created_at'];db.execute(text(f"INSERT INTO {TABLE_NAME} ({','.join(ins)}) VALUES ({','.join(':'+c for c in ins)})"),p)
    db.commit();return get_customer(db,rid)

def _decode(raw:bytes)->str:
    for enc in ('cp932','shift_jis','utf-8-sig','utf-8'):
        try:return raw.decode(enc)
        except UnicodeDecodeError:pass
    raise ValueError('CSV encoding is not supported')

def import_todokedl_csv(db:Session,raw:bytes)->dict[str,Any]:
    ensure_customer_master_table(db);reader=csv.DictReader(io.StringIO(_decode(raw)))
    missing=[x for x in TODOKEDL if x not in (reader.fieldnames or [])]
    if missing:raise ValueError('CSV required columns are missing: '+','.join(missing))
    inserted=updated=skipped=0;errors=[];now=datetime.now(timezone.utc).isoformat()
    for n,row in enumerate(reader,2):
        cid=str(row.get('お届け先コード','') or '').strip()
        if not cid:skipped+=1;errors.append({'row':n,'message':'お届け先コード is empty'});continue
        vals={dst:str(row.get(src,'') or '').strip() for src,dst in TODOKEDL.items()};vals.update({'source_system':'TODOKEDL','source_updated_at':now})
        old=db.execute(text(f"SELECT id FROM {TABLE_NAME} WHERE customer_id=:c"),{'c':cid}).first()
        if old:
            p={'id':old._mapping['id'],'source_system':'TODOKEDL','source_updated_at':now,'updated_at':now};sets=['source_system=:source_system','source_updated_at=:source_updated_at','updated_at=:updated_at']
            for f in TODOKEDL.values():
                if vals[f]:p[f]=vals[f];sets.append(f'{f}=:{f}')
            db.execute(text(f"UPDATE {TABLE_NAME} SET {','.join(sets)} WHERE id=:id"),p);updated+=1
        else:
            p={f:'' for f in ALL_FIELDS if f not in ('active',)};p.update(vals);p.update({'id':uuid4().hex,'customer_id':cid,'status_code':'ACTIVE','active':1,'note':'正式名称待维护','created_at':now,'updated_at':now})
            cols=[c for c in ALL_FIELDS if c in p];db.execute(text(f"INSERT INTO {TABLE_NAME} ({','.join(cols)}) VALUES ({','.join(':'+c for c in cols)})"),p);inserted+=1
    db.commit();return {'inserted':inserted,'updated':updated,'skipped':skipped,'errors':errors,'source_system':'TODOKEDL'}

def export_customers_csv(records:list[dict[str,Any]])->bytes:
    out=io.StringIO();w=csv.DictWriter(out,fieldnames=ALL_FIELDS,extrasaction='ignore');w.writeheader()
    for r in records:
        x=dict(r);x['active']=1 if r.get('active') else 0;w.writerow(x)
    return out.getvalue().encode('utf-8-sig')



def import_customer_rows(db: Session, rows: list[dict[str, Any]]) -> dict[str, Any]:
    ensure_customer_master_table(db)
    if not isinstance(rows, list):
        raise ValueError("rows must be a list")

    prepared: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Validate every row before the first write.
    for row_no, raw in enumerate(rows, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"row {row_no}: row must be an object")

        payload = dict(raw)
        customer_id = str(payload.get("customer_id", "") or "").strip()
        formal_name = str(payload.get("formal_name", "") or "").strip()

        if not customer_id:
            raise ValueError(f"row {row_no}: customer_id is required")
        if not formal_name:
            raise ValueError(f"row {row_no}: formal_name is required")
        if customer_id in seen:
            raise ValueError(f"row {row_no}: duplicate customer_id")
        seen.add(customer_id)

        existing = db.execute(
            text(f"SELECT id FROM {TABLE_NAME} WHERE customer_id=:customer_id"),
            {"customer_id": customer_id},
        ).first()
        if existing:
            payload["id"] = existing._mapping["id"]

        payload["customer_id"] = customer_id
        payload["formal_name"] = formal_name
        prepared.append(payload)

    inserted = 0
    updated = 0
    results = []

    for payload in prepared:
        is_update = bool(payload.get("id"))
        results.append(save_customer(db, payload))
        if is_update:
            updated += 1
        else:
            inserted += 1

    return {
        "imported": inserted + updated,
        "created": inserted,
        "updated": updated,
    }
