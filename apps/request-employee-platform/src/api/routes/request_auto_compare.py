from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.request_auto_compare_service import RequestAutoCompareService
router=APIRouter(prefix='/api/requests',tags=['request-auto-compare'])
class ParserJsonCompareRequest(BaseModel): legal_entity_id:str='TEST-JP-01'; pdf_json_path:str; excel_json_path:str
@router.post('/compare-parser-json')
def compare(req:ParserJsonCompareRequest,db:Session=Depends(get_db)):
 try: return RequestAutoCompareService(db).compare_parser_json_files(req.legal_entity_id,req.pdf_json_path,req.excel_json_path)
 except FileNotFoundError as e: raise HTTPException(404,str(e))
 except Exception as e: raise HTTPException(400,str(e))
