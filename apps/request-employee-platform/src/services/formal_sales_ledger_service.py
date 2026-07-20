from __future__ import annotations
from datetime import datetime,timezone
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.services.request_pending_review_resolution_service import ensure_review_audit_table
from src.services.request_pending_review_service import TABLE_NAME,get_pending_review

LEDGER_TABLE="formal_sales_request_ledger"

def ensure_sales_ledger_table(db:Session)->None:
    ensure_review_audit_table(db)
    cols={r[1] for r in db.execute(text(f"PRAGMA table_info({TABLE_NAME})")).all()}
    if "posted_at" not in cols:
        db.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN posted_at VARCHAR(64) NOT NULL DEFAULT ''"))
    if "sales_ledger_id" not in cols:
        db.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN sales_ledger_id VARCHAR(64) NOT NULL DEFAULT ''"))
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {LEDGER_TABLE}(
      id VARCHAR(64) PRIMARY KEY,
      pending_review_id VARCHAR(64) NOT NULL UNIQUE,
      request_no VARCHAR(255) NOT NULL UNIQUE,
      request_date VARCHAR(64) NOT NULL DEFAULT '',
      customer_id VARCHAR(255) NOT NULL DEFAULT '',
      customer_name VARCHAR(500) NOT NULL DEFAULT '',
      currency VARCHAR(16) NOT NULL DEFAULT '',
      subtotal VARCHAR(64) NOT NULL DEFAULT '',
      tax_amount VARCHAR(64) NOT NULL DEFAULT '',
      total_amount VARCHAR(64) NOT NULL DEFAULT '',
      excel_source VARCHAR(1000) NOT NULL DEFAULT '',
      pdf_source VARCHAR(1000) NOT NULL DEFAULT '',
      reviewed_by VARCHAR(255) NOT NULL DEFAULT '',
      review_note TEXT NOT NULL DEFAULT '',
      reviewed_at VARCHAR(64) NOT NULL DEFAULT '',
      posted_at VARCHAR(64) NOT NULL,
      status VARCHAR(64) NOT NULL DEFAULT 'ACTIVE'
    )"""))
    db.commit()

def _row(row:Any)->dict[str,Any]:
    return dict(row._mapping if hasattr(row,"_mapping") else row)

def post_approved_pending_review(db:Session,record_id:str,*,commit:bool=True)->dict[str,Any]:
    ensure_sales_ledger_table(db);pending=get_pending_review(db,record_id)
    if pending is None: raise LookupError("Business review record not found")
    if pending.get("status")!="APPROVED": raise ValueError("Only APPROVED business-review records can enter Sales Ledger")
    source_no=str(pending.get("source_request_no") or pending.get("request_no") or "")
    existing=db.execute(text(f"SELECT * FROM {LEDGER_TABLE} WHERE pending_review_id=:rid OR request_no=:no"),{"rid":record_id,"no":source_no}).first()
    if existing:
        row=_row(existing)
        if row.get("pending_review_id")==record_id:return {"status":"exists","ledger":row}
        raise ValueError("The request number already exists in the formal Sales Ledger. Use DUPLICATE instead of APPROVED.")
    lid=uuid4().hex;now=datetime.now(timezone.utc).isoformat();p={"id":lid,"pending_review_id":record_id,"request_no":source_no,"request_date":pending.get("request_date",""),"customer_id":pending.get("customer_id",""),"customer_name":pending.get("customer_name",""),"currency":pending.get("currency",""),"subtotal":pending.get("subtotal",""),"tax_amount":pending.get("tax_amount",""),"total_amount":pending.get("total_amount",""),"excel_source":pending.get("excel_source",""),"pdf_source":pending.get("pdf_source",""),"reviewed_by":pending.get("reviewed_by",""),"review_note":pending.get("review_note",""),"reviewed_at":pending.get("reviewed_at",""),"posted_at":now,"status":"ACTIVE"}
    db.execute(text(f"""INSERT INTO {LEDGER_TABLE}(id,pending_review_id,request_no,request_date,customer_id,customer_name,currency,subtotal,tax_amount,total_amount,excel_source,pdf_source,reviewed_by,review_note,reviewed_at,posted_at,status) VALUES(:id,:pending_review_id,:request_no,:request_date,:customer_id,:customer_name,:currency,:subtotal,:tax_amount,:total_amount,:excel_source,:pdf_source,:reviewed_by,:review_note,:reviewed_at,:posted_at,:status)"""),p)
    db.execute(text(f"UPDATE {TABLE_NAME} SET sales_ledger_id=:lid,posted_at=:now,updated_at=:now WHERE id=:id"),{"lid":lid,"now":now,"id":record_id})
    if commit: db.commit()
    row=db.execute(text(f"SELECT * FROM {LEDGER_TABLE} WHERE id=:id"),{"id":lid}).first();return {"status":"posted","ledger":_row(row)}

def list_sales_ledger(db:Session,customer_id:str="",customer_name:str="",request_no:str="",status:str="",limit:int=500):
    ensure_sales_ledger_table(db)
    clauses=[]; p={"limit":min(max(int(limit),1),1000)}
    for key,val in [("customer_id",customer_id),("customer_name",customer_name),("request_no",request_no)]:
        if val: clauses.append(f"{key} LIKE :{key}"); p[key]=f"%{val}%"
    if status: clauses.append("status=:status"); p["status"]=status
    where="WHERE "+" AND ".join(clauses) if clauses else ""
    rows=db.execute(text(f"SELECT * FROM {LEDGER_TABLE} {where} ORDER BY posted_at DESC LIMIT :limit"),p).all()
    return [_row(r) for r in rows]

def get_sales_ledger_record(db:Session,ledger_id:str):
    ensure_sales_ledger_table(db)
    row=db.execute(text(f"SELECT * FROM {LEDGER_TABLE} WHERE id=:id"),{"id":ledger_id}).first()
    return _row(row) if row else None
