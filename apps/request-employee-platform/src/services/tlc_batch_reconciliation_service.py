from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.services.tlc_batch_service import append_timeline,get_batch,transition_batch
TABLE_NAME="tlc_batch_reconciliation_link"
def ensure_table(db:Session)->None:
 db.execute(text(f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME}(id VARCHAR(64) PRIMARY KEY,batch_id VARCHAR(64) NOT NULL,reconciliation_id VARCHAR(128) NOT NULL,customer_id VARCHAR(128) NOT NULL,customer_name VARCHAR(500) NOT NULL DEFAULT '',period_sales_total VARCHAR(64) NOT NULL DEFAULT '0',period_payment_total VARCHAR(64) NOT NULL DEFAULT '0',closing_outstanding VARCHAR(64) NOT NULL DEFAULT '0',reconciliation_status VARCHAR(64) NOT NULL DEFAULT '',confirmed_by VARCHAR(255) NOT NULL DEFAULT '',confirmed_at VARCHAR(64) NOT NULL DEFAULT '',linked_by VARCHAR(255) NOT NULL,linked_at VARCHAR(64) NOT NULL,note TEXT NOT NULL DEFAULT '',UNIQUE(batch_id,reconciliation_id))"""));db.commit()
def _row(r:Any)->dict[str,Any]:return dict(r._mapping)
def create_link(db:Session,*,batch_id:str,reconciliation_id:str,customer_id:str,customer_name:str='',period_sales_total:str='0',period_payment_total:str='0',closing_outstanding:str='0',reconciliation_status:str='',confirmed_by:str='',confirmed_at:str='',linked_by:str,note:str=''):
 ensure_table(db);b=get_batch(db,batch_id)
 if not b:raise LookupError('Batch not found')
 if b['status'] not in {'BANK_IMPORTED','RECONCILING','FINISHED'}:raise ValueError('Batch must be BANK_IMPORTED, RECONCILING or FINISHED')
 reconciliation_id=str(reconciliation_id or '').strip();customer_id=str(customer_id or '').strip();linked_by=str(linked_by or '').strip()
 if not reconciliation_id:raise ValueError('reconciliation_id is required')
 if not customer_id:raise ValueError('customer_id is required')
 if not linked_by:raise ValueError('linked_by is required')
 ex=db.execute(text(f'SELECT * FROM {TABLE_NAME} WHERE batch_id=:b AND reconciliation_id=:r'),{'b':batch_id,'r':reconciliation_id}).first()
 if ex:return {'status':'exists','reconciliation_link':_row(ex)}
 rid=uuid4().hex;now=datetime.now(timezone.utc).isoformat()
 db.execute(text(f"""INSERT INTO {TABLE_NAME}(id,batch_id,reconciliation_id,customer_id,customer_name,period_sales_total,period_payment_total,closing_outstanding,reconciliation_status,confirmed_by,confirmed_at,linked_by,linked_at,note) VALUES(:id,:b,:r,:c,:cn,:s,:p,:o,:st,:cb,:ca,:lb,:la,:n)"""),{'id':rid,'b':batch_id,'r':reconciliation_id,'c':customer_id,'cn':customer_name or '','s':str(period_sales_total or '0'),'p':str(period_payment_total or '0'),'o':str(closing_outstanding or '0'),'st':str(reconciliation_status or ''),'cb':str(confirmed_by or ''),'ca':str(confirmed_at or ''),'lb':linked_by,'la':now,'n':str(note or '')})
 append_timeline(db,batch_id=batch_id,event_type='RECONCILIATION_LINKED',old_status=b['status'],new_status=b['status'],message=f'Reconciliation linked: {reconciliation_id}',operator=linked_by);db.commit()
 if b['status']=='BANK_IMPORTED':transition_batch(db,batch_id,new_status='RECONCILING',operator=linked_by,message='Customer reconciliation started')
 return {'status':'linked','reconciliation_link':_row(db.execute(text(f'SELECT * FROM {TABLE_NAME} WHERE id=:id'),{'id':rid}).first())}
def list_links(db:Session,batch_id:str):
 ensure_table(db)
 if not get_batch(db,batch_id):raise LookupError('Batch not found')
 return [_row(x) for x in db.execute(text(f'SELECT * FROM {TABLE_NAME} WHERE batch_id=:b ORDER BY linked_at DESC'),{'b':batch_id}).all()]
def summary(db:Session,batch_id:str):
 rows=list_links(db,batch_id);settled=sum(1 for r in rows if str(r['reconciliation_status']).upper() in {'SETTLED','NO_ACTIVITY'})
 return {'batch_id':batch_id,'reconciliation_count':len(rows),'settled_count':settled,'open_count':len(rows)-settled}
def finish_batch(db:Session,*,batch_id:str,operator:str,message:str=''):
 b=get_batch(db,batch_id)
 if not b:raise LookupError('Batch not found')
 if b['status']!='RECONCILING':raise ValueError('Batch must be RECONCILING')
 rows=list_links(db,batch_id)
 if not rows:raise ValueError('At least one reconciliation link is required')
 if any(str(r['reconciliation_status']).upper() not in {'SETTLED','NO_ACTIVITY'} for r in rows):raise ValueError('All linked reconciliations must be SETTLED or NO_ACTIVITY before finishing')
 return transition_batch(db,batch_id,new_status='FINISHED',operator=operator,message=message or 'All linked reconciliations completed')
