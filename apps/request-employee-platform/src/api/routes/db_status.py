from fastapi import APIRouter
from sqlalchemy import text
from src.db.session import get_engine
router=APIRouter(prefix='/api/db',tags=['database'])
@router.get('/status')
def db_status():
 try:
  with get_engine().connect() as c: v=c.execute(text('select 1')).scalar_one()
  return {'status':'ok','select_1':v}
 except Exception as e: return {'status':'error','error':str(e)}
