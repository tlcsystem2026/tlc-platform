from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.services.tlc_import_center_service import create_job, ensure_table as ensure_import_job_table, update_job

LINK_TABLE = "tlc_bank_csv_import_job_link"

def ensure_table(db: Session) -> None:
    ensure_import_job_table(db)
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {LINK_TABLE}(
      id VARCHAR(64) PRIMARY KEY,batch_id VARCHAR(64) NOT NULL,
      bank_import_id VARCHAR(255) NOT NULL,import_job_id VARCHAR(64) NOT NULL,
      bank_name VARCHAR(255) NOT NULL DEFAULT '',source_name VARCHAR(1000) NOT NULL DEFAULT '',
      source_reference VARCHAR(2000) NOT NULL,record_count INTEGER NOT NULL DEFAULT 0,
      success_count INTEGER NOT NULL DEFAULT 0,error_count INTEGER NOT NULL DEFAULT 0,
      duplicate_count INTEGER NOT NULL DEFAULT 0,registered_by VARCHAR(255) NOT NULL,
      registered_at VARCHAR(64) NOT NULL,note TEXT NOT NULL DEFAULT '',
      UNIQUE(batch_id,bank_import_id),UNIQUE(import_job_id))"""))
    db.commit()

def _row(row: Any) -> dict[str, Any]:
    return dict(row._mapping)

def register_bank_csv_import(db: Session, *, batch_id: str, bank_import_id: str,
 source_name: str, source_reference: str, registered_by: str, bank_name: str = '',
 record_count: int = 0, success_count: int = 0, error_count: int = 0,
 duplicate_count: int = 0, note: str = '') -> dict[str, Any]:
    ensure_table(db)
    bank_import_id=str(bank_import_id or '').strip(); source_reference=str(source_reference or '').strip(); registered_by=str(registered_by or '').strip()
    if not bank_import_id: raise ValueError('bank_import_id is required')
    if not source_reference: raise ValueError('source_reference is required')
    if not registered_by: raise ValueError('registered_by is required')
    existing=db.execute(text(f"SELECT * FROM {LINK_TABLE} WHERE batch_id=:b AND bank_import_id=:i"),{'b':batch_id,'i':bank_import_id}).first()
    if existing: return {'status':'exists','link':_row(existing)}
    record_count=max(int(record_count or 0),0); success_count=max(int(success_count or 0),0); error_count=max(int(error_count or 0),0); duplicate_count=max(int(duplicate_count or 0),0)
    made=create_job(db,batch_id=batch_id,import_type='BANK_CSV',source_name=str(source_name or ''),source_reference=source_reference,created_by=registered_by,message=f'Bank CSV import registered: {bank_import_id}')
    job=made['job']
    if made['status']=='created':
        job=update_job(db,job_id=job['id'],status='PROCESSING',operator=registered_by,record_count=record_count,message='Bank CSV processing started')
        job=update_job(db,job_id=job['id'],status='SUCCESS' if error_count==0 else 'ERROR',operator=registered_by,record_count=record_count,success_count=success_count,error_count=error_count,duplicate_count=duplicate_count,message='Bank CSV import completed')
    rid=uuid4().hex; now=datetime.now(timezone.utc).isoformat()
    db.execute(text(f"""INSERT INTO {LINK_TABLE}(id,batch_id,bank_import_id,import_job_id,bank_name,source_name,source_reference,record_count,success_count,error_count,duplicate_count,registered_by,registered_at,note)
      VALUES(:id,:b,:bi,:j,:bn,:sn,:sr,:rc,:sc,:ec,:dc,:u,:at,:n)"""),{'id':rid,'b':batch_id,'bi':bank_import_id,'j':job['id'],'bn':str(bank_name or ''),'sn':str(source_name or ''),'sr':source_reference,'rc':record_count,'sc':success_count,'ec':error_count,'dc':duplicate_count,'u':registered_by,'at':now,'n':str(note or '')})
    db.commit()
    row=db.execute(text(f"SELECT * FROM {LINK_TABLE} WHERE id=:id"),{'id':rid}).first()
    return {'status':'registered','link':_row(row),'job':job}

def list_links(db: Session, batch_id: str = ''):
    ensure_table(db)
    if batch_id:
        rows=db.execute(text(f"SELECT * FROM {LINK_TABLE} WHERE batch_id=:b ORDER BY registered_at DESC"),{'b':batch_id}).all()
    else:
        rows=db.execute(text(f"SELECT * FROM {LINK_TABLE} ORDER BY registered_at DESC")).all()
    return [_row(x) for x in rows]

def summary(db: Session, batch_id: str = ''):
    rows=list_links(db,batch_id)
    return {'batch_id':batch_id,'import_count':len(rows),'record_count':sum(int(x['record_count']) for x in rows),'success_count':sum(int(x['success_count']) for x in rows),'error_count':sum(int(x['error_count']) for x in rows),'duplicate_count':sum(int(x['duplicate_count']) for x in rows)}
