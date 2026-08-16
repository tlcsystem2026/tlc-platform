from __future__ import annotations
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
import os
import re
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.services.request_pending_review_resolution_service import ensure_review_audit_table
from src.services.request_pending_review_service import TABLE_NAME,get_pending_review
from src.services.tlc_customer_master_service import ensure_customer_master_table
from src.services.tlc_customer_name_identity_service import ensure_schema as ensure_customer_name_identity_schema

LEDGER_TABLE="formal_sales_request_ledger"
LEDGER_ADMIN_AUDIT_TABLE="formal_sales_ledger_admin_audit"

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
    ledger_columns={row[1] for row in db.execute(text(f"PRAGMA table_info({LEDGER_TABLE})")).all()}
    admin_columns={
      "voided_by":"VARCHAR(255) NOT NULL DEFAULT ''",
      "voided_at":"VARCHAR(64) NOT NULL DEFAULT ''",
      "void_reason":"TEXT NOT NULL DEFAULT ''",
    }
    for column,definition in admin_columns.items():
        if column not in ledger_columns:
            db.execute(text(f"ALTER TABLE {LEDGER_TABLE} ADD COLUMN {column} {definition}"))
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {LEDGER_ADMIN_AUDIT_TABLE}(
      id VARCHAR(64) PRIMARY KEY,
      ledger_id VARCHAR(64) NOT NULL,
      request_no VARCHAR(255) NOT NULL DEFAULT '',
      action VARCHAR(64) NOT NULL,
      operator VARCHAR(255) NOT NULL,
      reason TEXT NOT NULL,
      operated_at VARCHAR(64) NOT NULL,
      snapshot TEXT NOT NULL DEFAULT ''
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
    ensure_customer_name_identity_schema(db)
    clauses=[]; p={"limit":min(max(int(limit),1),1000)}
    if customer_id:
        clauses.append("l.customer_id LIKE :customer_id");p["customer_id"]=f"%{customer_id}%"
    if customer_name:
        clauses.append("""(
          l.customer_name LIKE :customer_name OR
          c.formal_name LIKE :customer_name OR c.hiragana_name LIKE :customer_name OR
          c.katakana_name LIKE :customer_name OR c.katakana_name_short LIKE :customer_name OR
          c.short_name LIKE :customer_name OR c.delivery_name_1 LIKE :customer_name OR
          c.delivery_name_2 LIKE :customer_name OR EXISTS (
            SELECT 1 FROM tlc_customer_name_identity ni
            WHERE ni.customer_record_id=c.id AND ni.active=1
              AND ni.name_value LIKE :customer_name
          )
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
          "c.shipper_code","c.status_code","c.note","c.source_system",
        ]
        master_names="EXISTS (SELECT 1 FROM tlc_customer_name_identity ni WHERE ni.customer_record_id=c.id AND ni.active=1 AND ni.name_value LIKE :keyword)"
        clauses.append("("+" OR ".join(
          f"CAST({column} AS TEXT) LIKE :keyword" for column in searchable
        )+" OR "+master_names+")");p["keyword"]=f"%{keyword}%"
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
             (SELECT GROUP_CONCAT(ni.name_value,' / ') FROM tlc_customer_name_identity ni
               WHERE ni.customer_record_id=c.id AND ni.active=1 AND ni.name_type<>'FORMAL') AS master_registered_names
      FROM {LEDGER_TABLE} l
      LEFT JOIN tlc_customer_master c ON c.customer_id=l.customer_id
      {where}
      ORDER BY l.posted_at DESC
      LIMIT :limit
    """),p).all()
    return [_row(r) for r in rows]


def sales_ledger_statistics(
    db:Session,
    date_from:str="",
    date_to:str="",
    customer_id:str="",
    customer_name:str="",
    status:str="ACTIVE",
)->dict[str,Any]:
    ensure_sales_ledger_table(db)
    clauses=[];params={}
    if date_from:
        clauses.append("request_date>=:date_from");params["date_from"]=date_from
    if date_to:
        clauses.append("request_date<=:date_to");params["date_to"]=date_to
    if customer_id:
        clauses.append("customer_id LIKE :customer_id");params["customer_id"]=f"%{customer_id}%"
    if customer_name:
        clauses.append("customer_name LIKE :customer_name");params["customer_name"]=f"%{customer_name}%"
    if status:
        clauses.append("status=:status");params["status"]=status
    where="WHERE "+" AND ".join(clauses) if clauses else ""
    rows=[_row(row) for row in db.execute(text(f"""SELECT * FROM {LEDGER_TABLE}
      {where} ORDER BY request_date,id"""),params).all()]

    def amount(value:Any)->Decimal:
        try:return Decimal(str(value or "0").replace(",","").strip() or "0")
        except (InvalidOperation,ValueError):return Decimal("0")

    amount_fields=(
      "subtotal","tax_amount","total_amount",
      "taxable_amount_10","tax_amount_10","tax_inclusive_amount_10",
      "taxable_amount_8","tax_amount_8","tax_inclusive_amount_8",
      "non_taxable_amount","tax_exempt_amount",
    )
    totals={field:Decimal("0") for field in amount_fields}
    by_customer:dict[str,dict[str,Any]]={};by_month:dict[str,dict[str,Any]]={}
    for row in rows:
        for field in amount_fields:totals[field]+=amount(row.get(field))
        customer_key=str(row.get("customer_id") or row.get("customer_name") or "(unknown)")
        customer=by_customer.setdefault(customer_key,{
          "customer_id":str(row.get("customer_id") or ""),
          "customer_name":str(row.get("customer_name") or ""),"count":0,"total_amount":Decimal("0")
        })
        customer["count"]+=1;customer["total_amount"]+=amount(row.get("total_amount"))
        month=str(row.get("request_date") or "")[:7] or "(unknown)"
        monthly=by_month.setdefault(month,{"business_month":month,"count":0,"total_amount":Decimal("0")})
        monthly["count"]+=1;monthly["total_amount"]+=amount(row.get("total_amount"))

    def serial(item:dict[str,Any])->dict[str,Any]:
        return {key:(str(value) if isinstance(value,Decimal) else value) for key,value in item.items()}
    return {
      "filters":{"date_from":date_from,"date_to":date_to,"customer_id":customer_id,"customer_name":customer_name,"status":status},
      "summary":{"count":len(rows),**{key:str(value) for key,value in totals.items()}},
      "by_customer":[serial(item) for item in sorted(by_customer.values(),key=lambda x:x["total_amount"],reverse=True)],
      "by_month":[serial(by_month[key]) for key in sorted(by_month,reverse=True)],
    }

def get_sales_ledger_record(db:Session,ledger_id:str):
    ensure_sales_ledger_table(db)
    row=db.execute(text(f"SELECT * FROM {LEDGER_TABLE} WHERE id=:id"),{"id":ledger_id}).first()
    return _row(row) if row else None


def _is_test_ledger(record:dict[str,Any])->bool:
    values=" ".join(str(record.get(key) or "") for key in (
      "request_no","customer_id","customer_name","reviewed_by","review_note"
    )).upper()
    return bool(re.search(r"(^|[^A-Z0-9])(TEST|ACCEPT|CARRY|PERIOD|M2T\d*|ATOMIC|BAD)([^A-Z0-9]|$)",values))


def _dependency_labels(db:Session,ledger_id:str)->list[str]:
    ignored={LEDGER_TABLE,LEDGER_ADMIN_AUDIT_TABLE,TABLE_NAME}
    labels=[]
    tables=[str(row[0]) for row in db.execute(text(
      "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )).all()]
    candidate_columns={"sales_ledger_id","ledger_id","formal_sales_ledger_id"}
    for table in tables:
        if table in ignored or not re.fullmatch(r"[A-Za-z0-9_]+",table):
            continue
        columns={str(row[1]) for row in db.execute(text(f"PRAGMA table_info({table})")).all()}
        for column in sorted(columns.intersection(candidate_columns)):
            count=int(db.execute(text(
              f"SELECT COUNT(*) FROM {table} WHERE {column}=:ledger_id"
            ),{"ledger_id":ledger_id}).scalar_one() or 0)
            if count:
                labels.append(f"{table}.{column} ({count})")
    return labels


def _audit_admin_action(db:Session,record:dict[str,Any],action:str,operator:str,reason:str,now:str)->None:
    import json
    db.execute(text(f"""INSERT INTO {LEDGER_ADMIN_AUDIT_TABLE}(
      id,ledger_id,request_no,action,operator,reason,operated_at,snapshot
    ) VALUES(:id,:ledger_id,:request_no,:action,:operator,:reason,:operated_at,:snapshot)"""),{
      "id":uuid4().hex,"ledger_id":record["id"],"request_no":record.get("request_no",""),
      "action":action,"operator":operator,"reason":reason,"operated_at":now,
      "snapshot":json.dumps(record,ensure_ascii=False,default=str),
    })


def bulk_void_sales_ledger(db:Session,ledger_ids:list[str],operator:str,reason:str)->dict[str,Any]:
    ensure_sales_ledger_table(db)
    ids=list(dict.fromkeys(str(item or "").strip() for item in ledger_ids if str(item or "").strip()))
    operator=str(operator or "").strip();reason=str(reason or "").strip()
    if not ids: raise ValueError("At least one Sales Ledger record must be selected")
    if not operator: raise ValueError("Operator is required")
    if not reason: raise ValueError("Void reason is required")
    records=[]
    for ledger_id in ids:
        record=get_sales_ledger_record(db,ledger_id)
        if record is None: raise LookupError(f"Sales Ledger record not found: {ledger_id}")
        records.append(record)
    now=datetime.now(timezone.utc).isoformat()
    for record in records:
        if record.get("status")!="VOID":
            _audit_admin_action(db,record,"VOID",operator,reason,now)
            db.execute(text(f"""UPDATE {LEDGER_TABLE}
              SET status='VOID',voided_by=:operator,voided_at=:now,void_reason=:reason
              WHERE id=:id"""),{"operator":operator,"now":now,"reason":reason,"id":record["id"]})
    db.commit()
    return {"status":"voided","count":len(records),"ledger_ids":[r["id"] for r in records]}


def cleanup_test_sales_ledger(db:Session,ledger_ids:list[str],operator:str,reason:str,role:str,confirmation:str)->dict[str,Any]:
    ensure_sales_ledger_table(db)
    ids=list(dict.fromkeys(str(item or "").strip() for item in ledger_ids if str(item or "").strip()))
    operator=str(operator or "").strip();reason=str(reason or "").strip()
    if str(role or "").strip().upper()!="SUPER_ADMIN": raise PermissionError("SUPER_ADMIN role is required")
    allowed_admins={item.strip() for item in os.getenv("TLC_SUPER_ADMIN_OPERATORS","super-admin").split(",") if item.strip()}
    if operator not in allowed_admins: raise PermissionError("Operator is not configured as a SUPER_ADMIN")
    if str(confirmation or "").strip()!="DELETE TEST DATA": raise ValueError("Confirmation text must be DELETE TEST DATA")
    if not ids: raise ValueError("At least one Sales Ledger record must be selected")
    if not operator: raise ValueError("Operator is required")
    if not reason: raise ValueError("Cleanup reason is required")
    records=[];failures=[]
    for ledger_id in ids:
        record=get_sales_ledger_record(db,ledger_id)
        if record is None:
            failures.append({"ledger_id":ledger_id,"request_no":"","reason":"record not found"});continue
        if not _is_test_ledger(record):
            failures.append({"ledger_id":ledger_id,"request_no":record.get("request_no",""),"reason":"not recognized as test data"});continue
        dependencies=_dependency_labels(db,ledger_id)
        if dependencies:
            failures.append({"ledger_id":ledger_id,"request_no":record.get("request_no",""),"reason":"linked data: "+", ".join(dependencies[:5])});continue
        records.append(record)
    if failures:
        return {"status":"blocked","deleted":0,"failures":failures[:10],"failure_count":len(failures)}
    now=datetime.now(timezone.utc).isoformat()
    for record in records:
        _audit_admin_action(db,record,"DELETE_TEST_DATA",operator,reason,now)
        db.execute(text(f"""UPDATE {TABLE_NAME}
          SET status='TEST_DATA_DELETED',sales_ledger_id='',posted_at='',updated_at=:now
          WHERE id=:pending_id AND sales_ledger_id=:ledger_id"""),{
          "now":now,"pending_id":record.get("pending_review_id",""),"ledger_id":record["id"]})
        db.execute(text(f"DELETE FROM {LEDGER_TABLE} WHERE id=:id"),{"id":record["id"]})
    db.commit()
    return {"status":"deleted","deleted":len(records),"ledger_ids":[r["id"] for r in records],"failures":[]}
