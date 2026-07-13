
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.services.tlc_monthly_close_checklist_service import ensure_tables as ensure_close_tables
from src.services.tlc_monthly_close_control_service import monthly_close_overview

CARRY_TABLE="tlc_monthly_close_carry_forward"
ALLOWED_STATUSES={"OPEN","CONFIRMED","RESOLVED","CANCELLED"}

def ensure_table(db:Session)->None:
    ensure_close_tables(db)
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {CARRY_TABLE}(
      id VARCHAR(64) PRIMARY KEY,source_month VARCHAR(32) NOT NULL,target_month VARCHAR(32) NOT NULL,
      source_batch_id VARCHAR(64) NOT NULL DEFAULT '',category VARCHAR(128) NOT NULL,
      reference_id VARCHAR(255) NOT NULL DEFAULT '',title VARCHAR(500) NOT NULL,
      amount VARCHAR(64) NOT NULL DEFAULT '0',currency VARCHAR(32) NOT NULL DEFAULT '',
      status VARCHAR(64) NOT NULL DEFAULT 'OPEN',reason TEXT NOT NULL DEFAULT '',
      resolution_note TEXT NOT NULL DEFAULT '',created_by VARCHAR(255) NOT NULL,
      created_at VARCHAR(64) NOT NULL,updated_by VARCHAR(255) NOT NULL DEFAULT '',
      updated_at VARCHAR(64) NOT NULL,
      UNIQUE(source_month,target_month,category,reference_id))"""))
    db.commit()

def _row(row:Any)->dict[str,Any]: return dict(row._mapping)

def _validate(source_month:str,target_month:str)->None:
    if not source_month or not target_month: raise ValueError("source_month and target_month are required")
    if target_month<=source_month: raise ValueError("target_month must be after source_month")

def create_carry_forward(db:Session,*,source_month:str,target_month:str,category:str,title:str,created_by:str,
                         source_batch_id:str="",reference_id:str="",amount:str="0",currency:str="",reason:str="")->dict[str,Any]:
    ensure_table(db)
    source_month=str(source_month or "").strip();target_month=str(target_month or "").strip()
    category=str(category or "").strip().upper();title=str(title or "").strip()
    created_by=str(created_by or "").strip();reference_id=str(reference_id or "").strip()
    _validate(source_month,target_month)
    if not category: raise ValueError("category is required")
    if not title: raise ValueError("title is required")
    if not created_by: raise ValueError("created_by is required")
    existing=db.execute(text(f"""SELECT * FROM {CARRY_TABLE}
      WHERE source_month=:s AND target_month=:t AND category=:c AND reference_id=:r"""),
      {"s":source_month,"t":target_month,"c":category,"r":reference_id}).first()
    if existing:return {"status":"exists","carry_forward":_row(existing)}
    now=datetime.now(timezone.utc).isoformat();item_id=uuid4().hex
    db.execute(text(f"""INSERT INTO {CARRY_TABLE}(
      id,source_month,target_month,source_batch_id,category,reference_id,title,amount,currency,
      status,reason,resolution_note,created_by,created_at,updated_by,updated_at
    ) VALUES(:id,:s,:t,:b,:c,:r,:title,:a,:cur,'OPEN',:reason,'',:u,:at,:u,:at)"""),
    {"id":item_id,"s":source_month,"t":target_month,"b":str(source_batch_id or ""),"c":category,
     "r":reference_id,"title":title,"a":str(amount or "0"),"cur":str(currency or ""),
     "reason":str(reason or ""),"u":created_by,"at":now})
    db.commit()
    row=db.execute(text(f"SELECT * FROM {CARRY_TABLE} WHERE id=:id"),{"id":item_id}).first()
    return {"status":"created","carry_forward":_row(row)}

def list_carry_forwards(db:Session,*,source_month:str="",target_month:str="",status:str="",limit:int=500)->list[dict[str,Any]]:
    ensure_table(db);clauses=[];params={"limit":min(max(int(limit),1),1000)}
    if source_month:clauses.append("source_month=:s");params["s"]=source_month
    if target_month:clauses.append("target_month=:t");params["t"]=target_month
    if status:
        status=status.strip().upper()
        if status not in ALLOWED_STATUSES:raise ValueError("Unsupported carry-forward status")
        clauses.append("status=:st");params["st"]=status
    where=f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows=db.execute(text(f"SELECT * FROM {CARRY_TABLE} {where} ORDER BY created_at LIMIT :limit"),params).all()
    return [_row(x) for x in rows]

def update_carry_forward(db:Session,*,item_id:str,status:str,operator:str,resolution_note:str="")->dict[str,Any]:
    ensure_table(db)
    current=db.execute(text(f"SELECT * FROM {CARRY_TABLE} WHERE id=:id"),{"id":item_id}).first()
    if not current:raise LookupError("Carry-forward item not found")
    status=str(status or "").strip().upper();operator=str(operator or "").strip()
    if status not in ALLOWED_STATUSES:raise ValueError("Unsupported carry-forward status")
    if not operator:raise ValueError("operator is required")
    db.execute(text(f"""UPDATE {CARRY_TABLE} SET status=:st,resolution_note=:n,
      updated_by=:u,updated_at=:at WHERE id=:id"""),
      {"id":item_id,"st":status,"n":str(resolution_note or ""),"u":operator,
       "at":datetime.now(timezone.utc).isoformat()})
    db.commit()
    row=db.execute(text(f"SELECT * FROM {CARRY_TABLE} WHERE id=:id"),{"id":item_id}).first()
    return _row(row)

def auto_generate_from_month(db:Session,*,source_month:str,target_month:str,operator:str)->dict[str,Any]:
    ensure_table(db);_validate(source_month,target_month)
    overview=monthly_close_overview(db,source_month);created=existing=0;items=[]
    for blocker in overview.get("blockers",[]):
        batch_id=blocker.get("batch_id","");batch_no=blocker.get("batch_no","")
        for i,detail in enumerate(blocker.get("items",[]),1):
            result=create_carry_forward(db,source_month=source_month,target_month=target_month,
              source_batch_id=batch_id,category="MONTH_CLOSE_BLOCKER",
              reference_id=f"{batch_id or 'MONTH'}:{i}:{detail}",
              title=f"{batch_no or source_month} - {detail}",created_by=operator,
              reason="Automatically generated from monthly close blocker")
            created+=result["status"]=="created";existing+=result["status"]=="exists";items.append(result["carry_forward"])
    return {"source_month":source_month,"target_month":target_month,
            "created_count":created,"existing_count":existing,"items":items}

def control_view(db:Session,business_month:str)->dict[str,Any]:
    incoming=list_carry_forwards(db,target_month=business_month,limit=1000)
    outgoing=list_carry_forwards(db,source_month=business_month,limit=1000)
    open_states={"OPEN","CONFIRMED"}
    return {"business_month":business_month,"incoming":incoming,"outgoing":outgoing,
      "incoming_open_count":sum(1 for x in incoming if x["status"] in open_states),
      "outgoing_open_count":sum(1 for x in outgoing if x["status"] in open_states),
      "incoming_resolved_count":sum(1 for x in incoming if x["status"]=="RESOLVED"),
      "outgoing_resolved_count":sum(1 for x in outgoing if x["status"]=="RESOLVED"),
      "close_blocked_by_outgoing":any(x["status"] in open_states for x in outgoing)}
