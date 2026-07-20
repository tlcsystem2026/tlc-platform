from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from fastapi.responses import HTMLResponse,Response
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_customer_master_service import MasterDeleteConflict,delete_customers,export_customers_csv,get_customer,import_customer_rows,import_todokedl_csv,list_customers,save_customer
router=APIRouter(tags=['tlc-customer-master'])

def _list(db,**kw):return list_customers(db,**kw)
@router.get('/api/tlc-customers')
def list_records(query:str='',customer_id:str='',formal_name:str='',katakana_name:str='',katakana_name_short:str='',delivery_name_1:str='',delivery_name_2:str='',phone_number:str='',postal_code:str='',address:str='',status_code:str='',source_system:str='',include_inactive:bool=True,limit:int=Query(500,ge=1,le=2000),db:Session=Depends(get_db)):
 return _list(db,query=query,customer_id=customer_id,formal_name=formal_name,katakana_name=katakana_name,katakana_name_short=katakana_name_short,delivery_name_1=delivery_name_1,delivery_name_2=delivery_name_2,phone_number=phone_number,postal_code=postal_code,address=address,status_code=status_code,source_system=source_system,include_inactive=include_inactive,limit=limit)
@router.post('/api/tlc-customers/import')
async def import_records(request:Request,db:Session=Depends(get_db)):
 try:
  content_type=request.headers.get('content-type','').lower()
  if 'application/json' in content_type:
   payload=await request.json()
   return import_customer_rows(db,payload.get('rows',[]))
  if 'multipart/form-data' in content_type:
   form=await request.form()
   upload=form.get('file')
   if upload is None or not hasattr(upload,'read'):raise ValueError('file is required')
   return import_todokedl_csv(db,await upload.read())
  raise ValueError('Content-Type must be application/json or multipart/form-data')
 except ValueError as e:
  db.rollback()
  raise HTTPException(400,str(e)) from e
@router.get('/api/tlc-customers/export.csv')
def export_records(query:str='',customer_id:str='',formal_name:str='',katakana_name:str='',katakana_name_short:str='',delivery_name_1:str='',delivery_name_2:str='',phone_number:str='',postal_code:str='',address:str='',status_code:str='',source_system:str='',include_inactive:bool=True,db:Session=Depends(get_db)):
 data=_list(db,query=query,customer_id=customer_id,formal_name=formal_name,katakana_name=katakana_name,katakana_name_short=katakana_name_short,delivery_name_1=delivery_name_1,delivery_name_2=delivery_name_2,phone_number=phone_number,postal_code=postal_code,address=address,status_code=status_code,source_system=source_system,include_inactive=include_inactive,limit=2000)
 return Response(export_customers_csv(data),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="tlc_customer_master.csv"'})

@router.post('/api/tlc-customers/delete-batch')
def delete_batch(payload:dict,db:Session=Depends(get_db)):
 try:return delete_customers(db,payload.get('ids',[]))
 except MasterDeleteConflict as e:
  raise HTTPException(409,detail={'message':str(e),'blocked':e.references}) from e
 except LookupError as e:raise HTTPException(404,str(e)) from e
 except ValueError as e:raise HTTPException(400,str(e)) from e

@router.delete('/api/tlc-customers/{record_id}')
def delete_record(record_id:str,db:Session=Depends(get_db)):
 try:return delete_customers(db,[record_id])
 except MasterDeleteConflict as e:
  raise HTTPException(409,detail={'message':str(e),'blocked':e.references}) from e
 except LookupError as e:raise HTTPException(404,str(e)) from e
 except ValueError as e:raise HTTPException(400,str(e)) from e

@router.get('/api/tlc-customers/{record_id}')
def get_record(record_id:str,db:Session=Depends(get_db)):
 r=get_customer(db,record_id)
 if r is None:raise HTTPException(404,'Customer not found')
 return r
@router.post('/api/tlc-customers')
def save_record(payload:dict,db:Session=Depends(get_db)):
 try:return save_customer(db,payload)
 except LookupError as e:raise HTTPException(404,str(e)) from e
 except ValueError as e:raise HTTPException(400,str(e)) from e
@router.get('/tlc-customer-master',response_class=HTMLResponse)
def page():return HTMLResponse((Path(__file__).parents[2]/'web/static/tlc_customer_master.html').read_text(encoding='utf-8'))
