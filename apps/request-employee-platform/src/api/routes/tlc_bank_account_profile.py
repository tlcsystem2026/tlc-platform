from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_bank_account_profile_service import list_profiles,save_profile,seed_banks
router=APIRouter(tags=['tlc-bank-account-profile'])
@router.get('/api/tlc-bank-accounts')
def listing(bank_code:str='',account_number:str='',db:Session=Depends(get_db)):
 seed_banks(db);return list_profiles(db,bank_code,account_number)
@router.post('/api/tlc-bank-accounts')
def saving(payload:dict,db:Session=Depends(get_db)):
 try:return save_profile(db,payload)
 except LookupError as e:raise HTTPException(404,str(e)) from e
 except ValueError as e:raise HTTPException(400,str(e)) from e
@router.get('/tlc-bank-account-master',response_class=HTMLResponse)
def page():return HTMLResponse((Path(__file__).parents[2]/'web'/'static'/'tlc_bank_account_master.html').read_text(encoding='utf-8'))
