
from __future__ import annotations
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session

CONFIRM_TABLE="tlc_customer_reconciliation_confirmation"
AUDIT_TABLE="tlc_customer_reconciliation_audit"
ALLOWED={"DRAFT","CONFIRMED","CORRECTED","REOPENED","CANCELLED"}

def ensure_tables(db:Session)->None:
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {CONFIRM_TABLE}(
      id VARCHAR(64) PRIMARY KEY,snapshot_id VARCHAR(64) NOT NULL UNIQUE,
      customer_id VARCHAR(255) NOT NULL,customer_name VARCHAR(500) NOT NULL DEFAULT '',
      status VARCHAR(64) NOT NULL DEFAULT 'DRAFT',
      sales_total VARCHAR(64) NOT NULL DEFAULT '0',payment_total VARCHAR(64) NOT NULL DEFAULT '0',
      unpaid_amount VARCHAR(64) NOT NULL DEFAULT '0',confirmed_sales_total VARCHAR(64) NOT NULL DEFAULT '0',
      confirmed_payment_total VARCHAR(64) NOT NULL DEFAULT '0',confirmed_unpaid_amount VARCHAR(64) NOT NULL DEFAULT '0',
      correction_reason TEXT NOT NULL DEFAULT '',note TEXT NOT NULL DEFAULT '',
      created_by VARCHAR(255) NOT NULL,created_at VARCHAR(64) NOT NULL,
      confirmed_by VARCHAR(255) NOT NULL DEFAULT '',confirmed_at VARCHAR(64) NOT NULL DEFAULT '',
      updated_by VARCHAR(255) NOT NULL DEFAULT '',updated_at VARCHAR(64) NOT NULL)"""))
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {AUDIT_TABLE}(
      id VARCHAR(64) PRIMARY KEY,confirmation_id VARCHAR(64) NOT NULL,snapshot_id VARCHAR(64) NOT NULL,
      customer_id VARCHAR(255) NOT NULL,event_type VARCHAR(128) NOT NULL,
      old_status VARCHAR(64) NOT NULL DEFAULT '',new_status VARCHAR(64) NOT NULL DEFAULT '',
      old_sales_total VARCHAR(64) NOT NULL DEFAULT '0',new_sales_total VARCHAR(64) NOT NULL DEFAULT '0',
      old_payment_total VARCHAR(64) NOT NULL DEFAULT '0',new_payment_total VARCHAR(64) NOT NULL DEFAULT '0',
      old_unpaid_amount VARCHAR(64) NOT NULL DEFAULT '0',new_unpaid_amount VARCHAR(64) NOT NULL DEFAULT '0',
      actor VARCHAR(255) NOT NULL,message TEXT NOT NULL DEFAULT '',event_at VARCHAR(64) NOT NULL)"""))
    db.commit()

def _row(r:Any)->dict[str,Any]: return dict(r._mapping)
def _dec(v:Any)->Decimal:
    try:return Decimal(str(v or "0").replace(",",""))
    except (InvalidOperation,ValueError):return Decimal("0")
def _fmt(v:Decimal)->str:
    s=format(v.quantize(Decimal("0.01")),"f")
    return s.rstrip("0").rstrip(".") if "." in s else s

def _audit(db:Session,rec:dict[str,Any],event:str,old_status:str,new_status:str,
           old_sales:str,new_sales:str,old_pay:str,new_pay:str,old_unpaid:str,new_unpaid:str,
           actor:str,message:str="")->None:
    db.execute(text(f"""INSERT INTO {AUDIT_TABLE}(
      id,confirmation_id,snapshot_id,customer_id,event_type,old_status,new_status,
      old_sales_total,new_sales_total,old_payment_total,new_payment_total,
      old_unpaid_amount,new_unpaid_amount,actor,message,event_at)
      VALUES(:id,:cid,:sid,:customer_id,:event,:old_status,:new_status,
      :old_sales,:new_sales,:old_pay,:new_pay,:old_unpaid,:new_unpaid,:actor,:message,:event_at)"""),
      {"id":uuid4().hex,"cid":rec["id"],"sid":rec["snapshot_id"],"customer_id":rec["customer_id"],
       "event":event,"old_status":old_status,"new_status":new_status,"old_sales":old_sales,
       "new_sales":new_sales,"old_pay":old_pay,"new_pay":new_pay,"old_unpaid":old_unpaid,
       "new_unpaid":new_unpaid,"actor":actor,"message":message,
       "event_at":datetime.now(timezone.utc).isoformat()})

def create_confirmation(db:Session,*,snapshot_id:str,operator:str,note:str="")->dict[str,Any]:
    ensure_tables(db);snapshot_id=str(snapshot_id or "").strip();operator=str(operator or "").strip()
    if not snapshot_id:raise ValueError("snapshot_id is required")
    if not operator:raise ValueError("operator is required")
    existing=db.execute(text(f"SELECT * FROM {CONFIRM_TABLE} WHERE snapshot_id=:sid"),{"sid":snapshot_id}).first()
    if existing:return {"status":"exists","confirmation":_row(existing)}
    snap=db.execute(text("SELECT * FROM tlc_customer_reconciliation_snapshot WHERE id=:id"),{"id":snapshot_id}).first()
    if not snap:raise LookupError("Reconciliation snapshot not found")
    s=_row(snap);now=datetime.now(timezone.utc).isoformat();cid=uuid4().hex
    db.execute(text(f"""INSERT INTO {CONFIRM_TABLE}(
      id,snapshot_id,customer_id,customer_name,status,sales_total,payment_total,unpaid_amount,
      confirmed_sales_total,confirmed_payment_total,confirmed_unpaid_amount,correction_reason,note,
      created_by,created_at,confirmed_by,confirmed_at,updated_by,updated_at)
      VALUES(:id,:sid,:customer_id,:customer_name,'DRAFT',:sales,:pay,:unpaid,:sales,:pay,:unpaid,'',:note,
      :operator,:now,'','',:operator,:now)"""),
      {"id":cid,"sid":snapshot_id,"customer_id":s["customer_id"],"customer_name":s.get("customer_name",""),
       "sales":s["sales_total"],"pay":s["payment_total"],"unpaid":s["unpaid_amount"],
       "note":str(note or ""),"operator":operator,"now":now})
    rec={"id":cid,"snapshot_id":snapshot_id,"customer_id":s["customer_id"]}
    _audit(db,rec,"CONFIRMATION_CREATED","","DRAFT","0",s["sales_total"],"0",s["payment_total"],"0",s["unpaid_amount"],operator,note)
    db.commit()
    row=db.execute(text(f"SELECT * FROM {CONFIRM_TABLE} WHERE id=:id"),{"id":cid}).first()
    return {"status":"created","confirmation":_row(row)}


def update_confirmation(db:Session,*,confirmation_id:str,status:str,operator:str,
                        confirmed_sales_total:str="",confirmed_payment_total:str="",
                        correction_reason:str="",note:str="")->dict[str,Any]:
    ensure_tables(db)
    current=db.execute(text(f"SELECT * FROM {CONFIRM_TABLE} WHERE id=:id"),{"id":confirmation_id}).first()
    if not current:raise LookupError("Reconciliation confirmation not found")
    rec=_row(current);status=str(status or "").strip().upper();operator=str(operator or "").strip()
    if status not in ALLOWED:raise ValueError("Unsupported confirmation status")
    if not operator:raise ValueError("operator is required")
    old=rec["status"]
    if old=="CANCELLED":raise ValueError("Cancelled confirmation cannot be changed")
    sales=_dec(confirmed_sales_total) if str(confirmed_sales_total or "").strip() else _dec(rec["confirmed_sales_total"])
    pay=_dec(confirmed_payment_total) if str(confirmed_payment_total or "").strip() else _dec(rec["confirmed_payment_total"])
    unpaid=sales-pay
    if status=="CORRECTED" and not str(correction_reason or "").strip():
        raise ValueError("correction_reason is required for CORRECTED status")
    if status=="CONFIRMED" and old not in {"DRAFT","REOPENED","CORRECTED"}:
        raise ValueError("Current status cannot be confirmed")
    if status=="REOPENED" and old!="CONFIRMED":
        raise ValueError("Only CONFIRMED record can be reopened")
    if status=="CORRECTED" and old not in {"DRAFT","REOPENED","CORRECTED"}:
        raise ValueError("Current status cannot be corrected")
    if status=="CANCELLED" and old=="CONFIRMED":
        raise ValueError("Confirmed record must be reopened before cancellation")
    now=datetime.now(timezone.utc).isoformat()
    confirmed_by=operator if status=="CONFIRMED" else rec["confirmed_by"]
    confirmed_at=now if status=="CONFIRMED" else rec["confirmed_at"]
    db.execute(text(f"""UPDATE {CONFIRM_TABLE} SET status=:status,
      confirmed_sales_total=:sales,confirmed_payment_total=:pay,confirmed_unpaid_amount=:unpaid,
      correction_reason=:reason,note=:note,confirmed_by=:confirmed_by,confirmed_at=:confirmed_at,
      updated_by=:operator,updated_at=:now WHERE id=:id"""),
      {"id":confirmation_id,"status":status,"sales":_fmt(sales),"pay":_fmt(pay),"unpaid":_fmt(unpaid),
       "reason":str(correction_reason or rec["correction_reason"] or ""),
       "note":str(note or rec["note"] or ""),"confirmed_by":confirmed_by,
       "confirmed_at":confirmed_at,"operator":operator,"now":now})
    _audit(db,rec,f"CONFIRMATION_{status}",old,status,rec["confirmed_sales_total"],_fmt(sales),
           rec["confirmed_payment_total"],_fmt(pay),rec["confirmed_unpaid_amount"],_fmt(unpaid),
           operator,str(correction_reason or note or ""))
    db.commit()
    row=db.execute(text(f"SELECT * FROM {CONFIRM_TABLE} WHERE id=:id"),{"id":confirmation_id}).first()
    return _row(row)

def list_confirmations(db:Session,*,customer_id:str="",status:str="",limit:int=200)->list[dict[str,Any]]:
    ensure_tables(db);clauses=[];params={"limit":min(max(int(limit),1),1000)}
    if customer_id:clauses.append("customer_id=:customer_id");params["customer_id"]=customer_id
    if status:
        status=status.strip().upper()
        if status not in ALLOWED:raise ValueError("Unsupported confirmation status")
        clauses.append("status=:status");params["status"]=status
    where=f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows=db.execute(text(f"SELECT * FROM {CONFIRM_TABLE} {where} ORDER BY created_at DESC LIMIT :limit"),params).all()
    return [_row(x) for x in rows]

def get_confirmation(db:Session,confirmation_id:str)->dict[str,Any]:
    ensure_tables(db)
    row=db.execute(text(f"SELECT * FROM {CONFIRM_TABLE} WHERE id=:id"),{"id":confirmation_id}).first()
    if not row:raise LookupError("Reconciliation confirmation not found")
    return _row(row)

def list_audit(db:Session,*,confirmation_id:str="",customer_id:str="",limit:int=500)->list[dict[str,Any]]:
    ensure_tables(db);clauses=[];params={"limit":min(max(int(limit),1),2000)}
    if confirmation_id:clauses.append("confirmation_id=:confirmation_id");params["confirmation_id"]=confirmation_id
    if customer_id:clauses.append("customer_id=:customer_id");params["customer_id"]=customer_id
    where=f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows=db.execute(text(f"SELECT * FROM {AUDIT_TABLE} {where} ORDER BY event_at DESC LIMIT :limit"),params).all()
    return [_row(x) for x in rows]
