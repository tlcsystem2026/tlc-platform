from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.services.tlc_batch_service import append_timeline, get_batch, transition_batch

TABLE_NAME="tlc_batch_bank_import_link"

def ensure_table(db:Session)->None:
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME}(
      id VARCHAR(64) PRIMARY KEY,batch_id VARCHAR(64) NOT NULL,
      bank_transaction_id VARCHAR(128) NOT NULL,bank_name VARCHAR(255) NOT NULL DEFAULT '',
      transaction_id VARCHAR(255) NOT NULL DEFAULT '',transaction_date VARCHAR(32) NOT NULL DEFAULT '',
      direction VARCHAR(32) NOT NULL DEFAULT '',amount VARCHAR(64) NOT NULL DEFAULT '0',
      counterparty VARCHAR(1000) NOT NULL DEFAULT '',linked_by VARCHAR(255) NOT NULL,
      linked_at VARCHAR(64) NOT NULL,note TEXT NOT NULL DEFAULT '',
      UNIQUE(batch_id,bank_transaction_id))"""))
    db.commit()

def _row(row:Any)->dict[str,Any]: return dict(row._mapping)

def create_link(db:Session,*,batch_id:str,bank_transaction_id:str,bank_name:str="",transaction_id:str="",
                transaction_date:str="",direction:str="",amount:str="0",counterparty:str="",
                linked_by:str,note:str="")->dict[str,Any]:
    ensure_table(db)
    batch=get_batch(db,batch_id)
    if not batch: raise LookupError("Batch not found")
    if batch["status"] not in {"LEDGER_POSTED","BANK_IMPORTED"}:
        raise ValueError("Batch must be LEDGER_POSTED or BANK_IMPORTED")
    bank_transaction_id=str(bank_transaction_id or "").strip(); linked_by=str(linked_by or "").strip()
    if not bank_transaction_id: raise ValueError("bank_transaction_id is required")
    if not linked_by: raise ValueError("linked_by is required")
    ex=db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE batch_id=:b AND bank_transaction_id=:t"),
                  {"b":batch_id,"t":bank_transaction_id}).first()
    if ex:return {"status":"exists","bank_link":_row(ex)}
    now=datetime.now(timezone.utc).isoformat(); rid=uuid4().hex
    db.execute(text(f"""INSERT INTO {TABLE_NAME}(
      id,batch_id,bank_transaction_id,bank_name,transaction_id,transaction_date,
      direction,amount,counterparty,linked_by,linked_at,note
    ) VALUES(:id,:b,:bt,:bn,:ti,:td,:d,:a,:c,:u,:at,:n)"""),
    {"id":rid,"b":batch_id,"bt":bank_transaction_id,"bn":str(bank_name or ""),
     "ti":str(transaction_id or ""),"td":str(transaction_date or ""),
     "d":str(direction or ""),"a":str(amount or "0"),"c":str(counterparty or ""),
     "u":linked_by,"at":now,"n":str(note or "")})
    append_timeline(db,batch_id=batch_id,event_type="BANK_TRANSACTION_LINKED",
      old_status=batch["status"],new_status=batch["status"],
      message=f"Bank transaction linked: {bank_transaction_id}",operator=linked_by)
    db.commit()
    if batch["status"]=="LEDGER_POSTED":
        transition_batch(db,batch_id,new_status="BANK_IMPORTED",operator=linked_by,
          message="Bank transactions linked to Batch")
    row=db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id"),{"id":rid}).first()
    return {"status":"linked","bank_link":_row(row)}

def list_links(db:Session,batch_id:str)->list[dict[str,Any]]:
    ensure_table(db)
    if not get_batch(db,batch_id): raise LookupError("Batch not found")
    rows=db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE batch_id=:b ORDER BY transaction_date,linked_at"),
                    {"b":batch_id}).all()
    return [_row(x) for x in rows]

def summary(db:Session,batch_id:str)->dict[str,Any]:
    rows=list_links(db,batch_id); credit=debit=0.0
    for r in rows:
        try:v=float(str(r["amount"]).replace(",",""))
        except Exception:v=0.0
        if str(r["direction"]).upper()=="CREDIT":credit+=v
        elif str(r["direction"]).upper()=="DEBIT":debit+=v
    fmt=lambda x:str(int(x) if x.is_integer() else x)
    return {"batch_id":batch_id,"transaction_count":len(rows),
            "credit_count":sum(1 for r in rows if str(r["direction"]).upper()=="CREDIT"),
            "debit_count":sum(1 for r in rows if str(r["direction"]).upper()=="DEBIT"),
            "credit_total":fmt(credit),"debit_total":fmt(debit)}
