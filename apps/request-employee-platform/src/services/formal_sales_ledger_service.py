from __future__ import annotations
from datetime import datetime,timezone
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.services.request_pending_review_resolution_service import ensure_review_audit_table
from src.services.request_pending_review_service import TABLE_NAME,get_pending_review
from src.services.tlc_customer_master_service import ensure_customer_master_table

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
    ledger_columns={
      row[1]
      for row in db.execute(
        text(f"PRAGMA table_info({LEDGER_TABLE})")
      ).all()
    }
    tax_columns={
      "taxable_amount_10":"VARCHAR(64) NOT NULL DEFAULT ''",
      "tax_amount_10":"VARCHAR(64) NOT NULL DEFAULT ''",
      "tax_inclusive_amount_10":"VARCHAR(64) NOT NULL DEFAULT ''",
      "taxable_amount_8":"VARCHAR(64) NOT NULL DEFAULT ''",
      "tax_amount_8":"VARCHAR(64) NOT NULL DEFAULT ''",
      "tax_inclusive_amount_8":"VARCHAR(64) NOT NULL DEFAULT ''",
      "non_taxable_amount":"VARCHAR(64) NOT NULL DEFAULT ''",
      "tax_exempt_amount":"VARCHAR(64) NOT NULL DEFAULT ''",
    }
    for column,definition in tax_columns.items():
        if column not in ledger_columns:
            db.execute(
                text(
                    f"ALTER TABLE {LEDGER_TABLE} "
                    f"ADD COLUMN {column} {definition}"
                )
            )
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
    lid=uuid4().hex;now=datetime.now(timezone.utc).isoformat();p={"id":lid,"pending_review_id":record_id,"request_no":source_no,"request_date":pending.get("request_date",""),"customer_id":pending.get("customer_id",""),"customer_name":pending.get("customer_name",""),"currency":pending.get("currency",""),"subtotal":pending.get("subtotal",""),"tax_amount":pending.get("tax_amount",""),"total_amount":pending.get("total_amount",""),
       "taxable_amount_10":pending.get("taxable_amount_10",""),"tax_amount_10":pending.get("tax_amount_10",""),
       "tax_inclusive_amount_10":pending.get("tax_inclusive_amount_10",""),"taxable_amount_8":pending.get("taxable_amount_8",""),
       "tax_amount_8":pending.get("tax_amount_8",""),"tax_inclusive_amount_8":pending.get("tax_inclusive_amount_8",""),
       "non_taxable_amount":pending.get("non_taxable_amount",""),"tax_exempt_amount":pending.get("tax_exempt_amount",""),
       "excel_source":pending.get("excel_source",""),"pdf_source":pending.get("pdf_source",""),"reviewed_by":pending.get("reviewed_by",""),"review_note":pending.get("review_note",""),"reviewed_at":pending.get("reviewed_at",""),"posted_at":now,"status":"ACTIVE"}
    db.execute(text(f"""INSERT INTO {LEDGER_TABLE}(
      id,pending_review_id,request_no,request_date,customer_id,customer_name,
      currency,subtotal,tax_amount,total_amount,
      taxable_amount_10,tax_amount_10,tax_inclusive_amount_10,
      taxable_amount_8,tax_amount_8,tax_inclusive_amount_8,
      non_taxable_amount,tax_exempt_amount,
      excel_source,pdf_source,reviewed_by,review_note,
      reviewed_at,posted_at,status
    ) VALUES(
      :id,:pending_review_id,:request_no,:request_date,:customer_id,:customer_name,
      :currency,:subtotal,:tax_amount,:total_amount,
      :taxable_amount_10,:tax_amount_10,:tax_inclusive_amount_10,
      :taxable_amount_8,:tax_amount_8,:tax_inclusive_amount_8,
      :non_taxable_amount,:tax_exempt_amount,
      :excel_source,:pdf_source,:reviewed_by,:review_note,
      :reviewed_at,:posted_at,:status
    )"""),p)
    db.execute(text(f"UPDATE {TABLE_NAME} SET sales_ledger_id=:lid,posted_at=:now,updated_at=:now WHERE id=:id"),{"lid":lid,"now":now,"id":record_id})
    if commit: db.commit()
    row=db.execute(text(f"SELECT * FROM {LEDGER_TABLE} WHERE id=:id"),{"id":lid}).first();return {"status":"posted","ledger":_row(row)}

def list_sales_ledger(
    db:Session,
    customer_id:str="",
    customer_name:str="",
    request_no:str="",
    status:str="",
    keyword:str="",
    limit:int=500,
):
    ensure_sales_ledger_table(db)
    ensure_customer_master_table(db)
    clauses=[]; p={"limit":min(max(int(limit),1),1000)}
    if customer_id:
        clauses.append("l.customer_id LIKE :customer_id");p["customer_id"]=f"%{customer_id}%"
    if customer_name:
        clauses.append("""(
          l.customer_name LIKE :customer_name OR
          c.formal_name LIKE :customer_name OR c.hiragana_name LIKE :customer_name OR
          c.katakana_name LIKE :customer_name OR c.katakana_name_short LIKE :customer_name OR
          c.short_name LIKE :customer_name OR c.delivery_name_1 LIKE :customer_name OR
          c.delivery_name_2 LIKE :customer_name OR c.alias_1 LIKE :customer_name OR
          c.alias_2 LIKE :customer_name OR c.alias_3 LIKE :customer_name OR
          c.alias_4 LIKE :customer_name OR c.alias_5 LIKE :customer_name
        )""");p["customer_name"]=f"%{customer_name}%"
    if request_no:
        clauses.append("l.request_no LIKE :request_no");p["request_no"]=f"%{request_no}%"
    if status: clauses.append("l.status=:status"); p["status"]=status
    if keyword:
        searchable=[
          "l.id","l.pending_review_id","l.request_no","l.request_date",
          "l.customer_id","l.customer_name","l.currency","l.subtotal",
          "l.tax_amount","l.total_amount","l.excel_source","l.pdf_source",
          "l.reviewed_by","l.review_note","l.reviewed_at","l.posted_at","l.status",
          "l.taxable_amount_10","l.tax_amount_10","l.tax_inclusive_amount_10",
          "l.taxable_amount_8","l.tax_amount_8","l.tax_inclusive_amount_8",
          "l.non_taxable_amount","l.tax_exempt_amount",
          "c.customer_id","c.formal_name","c.hiragana_name","c.katakana_name",
          "c.katakana_name_short","c.short_name","c.delivery_name_1",
          "c.delivery_name_2","c.postal_code","c.address_1","c.address_2",
          "c.phone_number","c.email_address","c.jis_municipality_code",
          "c.shipper_code","c.alias_1","c.alias_2","c.alias_3","c.alias_4",
          "c.alias_5","c.status_code","c.note","c.source_system",
        ]
        clauses.append("("+" OR ".join(
          f"CAST({column} AS TEXT) LIKE :keyword" for column in searchable
        )+")");p["keyword"]=f"%{keyword}%"
    where="WHERE "+" AND ".join(clauses) if clauses else ""
    rows=db.execute(text(f"""
      SELECT l.*,
             c.formal_name AS master_formal_name,
             c.hiragana_name AS master_hiragana_name,
             c.katakana_name AS master_katakana_name,
             c.katakana_name_short AS master_katakana_name_short,
             c.short_name AS master_short_name,
             c.delivery_name_1 AS master_delivery_name_1,
             c.delivery_name_2 AS master_delivery_name_2,
             c.alias_1 AS master_alias_1,c.alias_2 AS master_alias_2,
             c.alias_3 AS master_alias_3,c.alias_4 AS master_alias_4,
             c.alias_5 AS master_alias_5
      FROM {LEDGER_TABLE} l
      LEFT JOIN tlc_customer_master c ON c.customer_id=l.customer_id
      {where}
      ORDER BY l.posted_at DESC
      LIMIT :limit
    """),p).all()
    return [_row(r) for r in rows]

def get_sales_ledger_record(db:Session,ledger_id:str):
    ensure_sales_ledger_table(db)
    row=db.execute(text(f"SELECT * FROM {LEDGER_TABLE} WHERE id=:id"),{"id":ledger_id}).first()
    return _row(row) if row else None
