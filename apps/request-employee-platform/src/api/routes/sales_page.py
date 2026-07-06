from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
router=APIRouter(tags=['sales'])
@router.get('/sales',response_class=HTMLResponse)
def page(): return (Path(__file__).parents[2]/'web'/'static'/'sales.html').read_text(encoding='utf-8')
