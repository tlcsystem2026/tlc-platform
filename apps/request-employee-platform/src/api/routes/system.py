from fastapi import APIRouter
from src.core.settings import get_settings
router=APIRouter(prefix='/api/system',tags=['system'])
@router.get('/runtime')
def runtime():
 s=get_settings(); return {'environment':s.env,'version':'0.30.2-clean-true-full','dashboard':'/dashboard','review':'/review','sales':'/sales','docs':'/docs','db_status':'/api/db/status'}
