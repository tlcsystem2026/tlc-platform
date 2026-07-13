
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session

CASE_TABLE="tlc_customer_reconciliation_case"
AUDIT_TABLE="tlc_customer_reconciliation_audit"
ALLOWED={"DRAFT","CONFIRMED","CORRECTION_REQUESTED","CORRECTED","CANCELLED"}

def _ensure_columns(db:Session,table_name:str,definitions:dict[str,str])->None:
    existing={str(r[1]) for r in db.execute(text(f"PRAGMA table_info({table_name})")).all()}
    for name,definition in definitions.items():
        if name not in existing:
            db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {definition}"))

def ensure_tables(db:Session)->None:
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {CASE_TABLE}(
      id VARCHAR(64) PRIMARY KEY,snapshot_id VARCHAR(64) NOT NULL UNIQUE,
      customer_id VARCHAR(255) NOT NULL,customer_name VARCHAR(500) NOT NULL DEFAULT '',
      previous_request_cutoff VARCHAR(32) NOT NULL,current_request_cutoff VARCHAR(32) NOT NULL,
      previous_bank_cutoff VARCHAR(32) NOT NULL,current_bank_cutoff VARCHAR(32) NOT NULL,
      sales_total VARCHAR(64) NOT NULL DEFAULT '0',payment_total VARCHAR(64) NOT NULL DEFAULT '0',
      unpaid_amount VARCHAR(64) NOT NULL DEFAULT '0',adjusted_sales_total VARCHAR(64) NOT NULL DEFAULT '0',
      adjusted_payment_total VARCHAR(64) NOT NULL DEFAULT '0',adjusted_unpaid_amount VARCHAR(64) NOT NULL DEFAULT '0',
      status VARCHAR(64) NOT NULL DEFAULT 'DRAFT',confirmation_note TEXT NOT NULL DEFAULT '',
      correction_reason TEXT NOT NULL DEFAULT '',confirmed_by VARCHAR(255) NOT NULL DEFAULT '',
      confirmed_at VARCHAR(64) NOT NULL DEFAULT '',corrected_by VARCHAR(255) NOT NULL DEFAULT '',
      corrected_at VARCHAR(64) NOT NULL DEFAULT '',created_by VARCHAR(255) NOT NULL,
      created_at VARCHAR(64) NOT NULL,updated_by VARCHAR(255) NOT NULL,updated_at VARCHAR(64) NOT NULL)"""))
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {AUDIT_TABLE}(
      id VARCHAR(64) PRIMARY KEY,reconciliation_id VARCHAR(64) NOT NULL,snapshot_id VARCHAR(64) NOT NULL,
      event_type VARCHAR(128) NOT NULL,actor VARCHAR(255) NOT NULL,event_at VARCHAR(64) NOT NULL,
      old_status VARCHAR(64) NOT NULL DEFAULT '',new_status VARCHAR(64) NOT NULL DEFAULT '',
      old_sales_total VARCHAR(64) NOT NULL DEFAULT '',new_sales_total VARCHAR(64) NOT NULL DEFAULT '',
      old_payment_total VARCHAR(64) NOT NULL DEFAULT '',new_payment_total VARCHAR(64) NOT NULL DEFAULT '',
      old_unpaid_amount VARCHAR(64) NOT NULL DEFAULT '',new_unpaid_amount VARCHAR(64) NOT NULL DEFAULT '',
      message TEXT NOT NULL DEFAULT '')"""))
    _ensure_columns(db,CASE_TABLE,{
      "snapshot_id":"VARCHAR(64) NOT NULL DEFAULT ''","customer_id":"VARCHAR(255) NOT NULL DEFAULT ''",
      "customer_name":"VARCHAR(500) NOT NULL DEFAULT ''","previous_request_cutoff":"VARCHAR(32) NOT NULL DEFAULT ''",
      "current_request_cutoff":"VARCHAR(32) NOT NULL DEFAULT ''","previous_bank_cutoff":"VARCHAR(32) NOT NULL DEFAULT ''",
      "current_bank_cutoff":"VARCHAR(32) NOT NULL DEFAULT ''","sales_total":"VARCHAR(64) NOT NULL DEFAULT '0'",
      "payment_total":"VARCHAR(64) NOT NULL DEFAULT '0'","unpaid_amount":"VARCHAR(64) NOT NULL DEFAULT '0'",
      "adjusted_sales_total":"VARCHAR(64) NOT NULL DEFAULT '0'","adjusted_payment_total":"VARCHAR(64) NOT NULL DEFAULT '0'",
      "adjusted_unpaid_amount":"VARCHAR(64) NOT NULL DEFAULT '0'","status":"VARCHAR(64) NOT NULL DEFAULT 'DRAFT'",
      "confirmation_note":"TEXT NOT NULL DEFAULT ''","correction_reason":"TEXT NOT NULL DEFAULT ''",
      "confirmed_by":"VARCHAR(255) NOT NULL DEFAULT ''","confirmed_at":"VARCHAR(64) NOT NULL DEFAULT ''",
      "corrected_by":"VARCHAR(255) NOT NULL DEFAULT ''","corrected_at":"VARCHAR(64) NOT NULL DEFAULT ''",
      "created_by":"VARCHAR(255) NOT NULL DEFAULT ''","created_at":"VARCHAR(64) NOT NULL DEFAULT ''",
      "updated_by":"VARCHAR(255) NOT NULL DEFAULT ''","updated_at":"VARCHAR(64) NOT NULL DEFAULT ''"
    })
    _ensure_columns(db,AUDIT_TABLE,{
      "reconciliation_id":"VARCHAR(64) NOT NULL DEFAULT ''","snapshot_id":"VARCHAR(64) NOT NULL DEFAULT ''",
      "event_type":"VARCHAR(128) NOT NULL DEFAULT ''","actor":"VARCHAR(255) NOT NULL DEFAULT ''",
      "event_at":"VARCHAR(64) NOT NULL DEFAULT ''","old_status":"VARCHAR(64) NOT NULL DEFAULT ''",
      "new_status":"VARCHAR(64) NOT NULL DEFAULT ''","old_sales_total":"VARCHAR(64) NOT NULL DEFAULT ''",
      "new_sales_total":"VARCHAR(64) NOT NULL DEFAULT ''","old_payment_total":"VARCHAR(64) NOT NULL DEFAULT ''",
      "new_payment_total":"VARCHAR(64) NOT NULL DEFAULT ''","old_unpaid_amount":"VARCHAR(64) NOT NULL DEFAULT ''",
      "new_unpaid_amount":"VARCHAR(64) NOT NULL DEFAULT ''","message":"TEXT NOT NULL DEFAULT ''"
    })
    db.commit()

def row(x:Any)->dict[str,Any]: return dict(x._mapping)
def dec(v:Any)->Decimal: return Decimal(str(v or "0").replace(",",""))
def fmt(v:Decimal)->str:
    s=format(v.quantize(Decimal("0.01")),"f")
    return s.rstrip("0").rstrip(".") if "." in s else s

def audit(db:Session,rec:dict[str,Any],event:str,actor:str,old_status:str,new_status:str,
          new_sales:str|None=None,new_payment:str|None=None,new_unpaid:str|None=None,message:str="")->None:
    db.execute(text(f"""INSERT INTO {AUDIT_TABLE}(
      id,reconciliation_id,snapshot_id,event_type,actor,event_at,old_status,new_status,
      old_sales_total,new_sales_total,old_payment_total,new_payment_total,
      old_unpaid_amount,new_unpaid_amount,message)
      VALUES(:id,:rid,:sid,:event,:actor,:at,:old,:new,:os,:ns,:op,:np,:ou,:nu,:msg)"""),
      {"id":uuid4().hex,"rid":rec["id"],"sid":rec["snapshot_id"],"event":event,"actor":actor,
       "at":datetime.now(timezone.utc).isoformat(),"old":old_status,"new":new_status,
       "os":rec.get("adjusted_sales_total",""),"ns":new_sales if new_sales is not None else rec.get("adjusted_sales_total",""),
       "op":rec.get("adjusted_payment_total",""),"np":new_payment if new_payment is not None else rec.get("adjusted_payment_total",""),
       "ou":rec.get("adjusted_unpaid_amount",""),"nu":new_unpaid if new_unpaid is not None else rec.get("adjusted_unpaid_amount",""),
       "msg":message})

def create_case(db:Session,*,snapshot_id:str,operator:str)->dict[str,Any]:
    ensure_tables(db);snapshot_id=snapshot_id.strip();operator=operator.strip()
    if not snapshot_id: raise ValueError("snapshot_id is required")
    if not operator: raise ValueError("operator is required")
    existing=db.execute(text(f"SELECT * FROM {CASE_TABLE} WHERE snapshot_id=:s"),{"s":snapshot_id}).first()
    if existing:return {"status":"exists","reconciliation":row(existing)}
    snap=db.execute(text("SELECT * FROM tlc_customer_reconciliation_snapshot WHERE id=:id"),{"id":snapshot_id}).first()
    if not snap: raise LookupError("Reconciliation snapshot not found")
    s=row(snap);rid=uuid4().hex;now=datetime.now(timezone.utc).isoformat()
    db.execute(text(f"""INSERT INTO {CASE_TABLE}(
      id,snapshot_id,customer_id,customer_name,previous_request_cutoff,current_request_cutoff,
      previous_bank_cutoff,current_bank_cutoff,sales_total,payment_total,unpaid_amount,
      adjusted_sales_total,adjusted_payment_total,adjusted_unpaid_amount,status,
      created_by,created_at,updated_by,updated_at)
      VALUES(:id,:sid,:cid,:cname,:pr,:cr,:pb,:cb,:sales,:pay,:unpaid,:sales,:pay,:unpaid,'DRAFT',:op,:now,:op,:now)"""),
      {"id":rid,"sid":snapshot_id,"cid":s["customer_id"],"cname":s.get("customer_name",""),
       "pr":s["previous_request_cutoff"],"cr":s["current_request_cutoff"],
       "pb":s["previous_bank_cutoff"],"cb":s["current_bank_cutoff"],
       "sales":s["sales_total"],"pay":s["payment_total"],"unpaid":s["unpaid_amount"],"op":operator,"now":now})
    rec=row(db.execute(text(f"SELECT * FROM {CASE_TABLE} WHERE id=:id"),{"id":rid}).first())
    audit(db,rec,"CASE_CREATED",operator,"","DRAFT",message="Created from snapshot");db.commit()
    return {"status":"created","reconciliation":rec}

def get_case(db:Session,rid:str)->dict[str,Any]:
    ensure_tables(db);r=db.execute(text(f"SELECT * FROM {CASE_TABLE} WHERE id=:id"),{"id":rid}).first()
    if not r:raise LookupError("Reconciliation case not found")
    return row(r)

def confirm(db:Session,*,rid:str,operator:str,note:str="")->dict[str,Any]:
    rec=get_case(db,rid);operator=operator.strip()
    if not operator:raise ValueError("operator is required")
    if rec["status"] not in {"DRAFT","CORRECTED"}:raise ValueError("Only DRAFT or CORRECTED case can be confirmed")
    now=datetime.now(timezone.utc).isoformat()
    db.execute(text(f"""UPDATE {CASE_TABLE} SET status='CONFIRMED',confirmation_note=:n,
      confirmed_by=:op,confirmed_at=:now,updated_by=:op,updated_at=:now WHERE id=:id"""),
      {"n":note,"op":operator,"now":now,"id":rid})
    audit(db,rec,"CASE_CONFIRMED",operator,rec["status"],"CONFIRMED",message=note);db.commit()
    return get_case(db,rid)

def request_correction(db:Session,*,rid:str,operator:str,reason:str)->dict[str,Any]:
    rec=get_case(db,rid);operator=operator.strip();reason=reason.strip()
    if not operator:raise ValueError("operator is required")
    if not reason:raise ValueError("correction reason is required")
    if rec["status"]!="CONFIRMED":raise ValueError("Only CONFIRMED case can request correction")
    now=datetime.now(timezone.utc).isoformat()
    db.execute(text(f"""UPDATE {CASE_TABLE} SET status='CORRECTION_REQUESTED',correction_reason=:r,
      updated_by=:op,updated_at=:now WHERE id=:id"""),{"r":reason,"op":operator,"now":now,"id":rid})
    audit(db,rec,"CORRECTION_REQUESTED",operator,"CONFIRMED","CORRECTION_REQUESTED",message=reason);db.commit()
    return get_case(db,rid)

def apply_correction(db:Session,*,rid:str,operator:str,sales:str,payment:str,note:str="")->dict[str,Any]:
    rec=get_case(db,rid);operator=operator.strip()
    if not operator:raise ValueError("operator is required")
    if rec["status"]!="CORRECTION_REQUESTED":raise ValueError("Case must be CORRECTION_REQUESTED")
    ns,np=dec(sales),dec(payment);nu=ns-np;now=datetime.now(timezone.utc).isoformat()
    fs,fp,fu=fmt(ns),fmt(np),fmt(nu)
    db.execute(text(f"""UPDATE {CASE_TABLE} SET adjusted_sales_total=:s,adjusted_payment_total=:p,
      adjusted_unpaid_amount=:u,status='CORRECTED',corrected_by=:op,corrected_at=:now,
      updated_by=:op,updated_at=:now WHERE id=:id"""),{"s":fs,"p":fp,"u":fu,"op":operator,"now":now,"id":rid})
    audit(db,rec,"CORRECTION_APPLIED",operator,"CORRECTION_REQUESTED","CORRECTED",fs,fp,fu,note);db.commit()
    return get_case(db,rid)

def cancel(db:Session,*,rid:str,operator:str,note:str="")->dict[str,Any]:
    rec=get_case(db,rid);operator=operator.strip()
    if not operator:raise ValueError("operator is required")
    if rec["status"]=="CANCELLED":return rec
    now=datetime.now(timezone.utc).isoformat()
    db.execute(text(f"UPDATE {CASE_TABLE} SET status='CANCELLED',updated_by=:op,updated_at=:now WHERE id=:id"),
      {"op":operator,"now":now,"id":rid})
    audit(db,rec,"CASE_CANCELLED",operator,rec["status"],"CANCELLED",message=note);db.commit()
    return get_case(db,rid)

def list_cases(db:Session,*,customer_id:str="",status:str="",limit:int=500)->list[dict[str,Any]]:
    ensure_tables(db);clauses=[];params={"limit":min(max(int(limit),1),1000)}
    if customer_id:clauses.append("customer_id=:cid");params["cid"]=customer_id
    if status:
        status=status.strip().upper()
        if status not in ALLOWED:raise ValueError("Unsupported reconciliation status")
        clauses.append("status=:st");params["st"]=status
    where=f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return [row(x) for x in db.execute(text(f"SELECT * FROM {CASE_TABLE} {where} ORDER BY updated_at DESC LIMIT :limit"),params).all()]

def list_audit(db:Session,*,rid:str,limit:int=1000)->list[dict[str,Any]]:
    ensure_tables(db)
    return [row(x) for x in db.execute(text(f"""SELECT * FROM {AUDIT_TABLE}
      WHERE reconciliation_id=:id ORDER BY event_at DESC LIMIT :limit"""),
      {"id":rid,"limit":min(max(int(limit),1),2000)}).all()]
