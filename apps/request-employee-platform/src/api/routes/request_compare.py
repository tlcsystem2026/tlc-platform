from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.domain.request_compare import RequestSnapshot
from src.services.request_compare_persistence_service import RequestComparePersistenceService
from src.repositories.review_repository import ReviewRepository
router=APIRouter(prefix='/api/requests',tags=['request-compare'])
class CompareRequest(BaseModel): legal_entity_id:str='TEST-JP-01'; pdf:RequestSnapshot; excel:RequestSnapshot
class ResolveRequest(BaseModel): note:str; assignee:str=''
@router.post('/compare')
def compare(req:CompareRequest,db:Session=Depends(get_db)): return RequestComparePersistenceService(db).compare_and_persist(req.legal_entity_id,req.pdf,req.excel)
@router.get('/review-tasks')
def tasks(limit:int=100,db:Session=Depends(get_db)):
 rows=ReviewRepository(db).list_open(limit); return [{'id':x.id,'business_key':x.business_key,'status':x.status,'priority':x.priority,'title_zh':x.title_zh,'title_ja':x.title_ja,'detail':x.detail_json} for x in rows]
@router.post('/review-tasks/{task_id}/resolve')
def resolve(task_id:str,req:ResolveRequest,db:Session=Depends(get_db)):
 t=ReviewRepository(db).resolve(task_id,req.note,req.assignee)
 if not t: raise HTTPException(404,'review task not found')
 return {'id':t.id,'status':t.status}
