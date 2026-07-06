from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
router=APIRouter(tags=['review'])
@router.get('/review',response_class=HTMLResponse)
def page(): return (Path(__file__).parents[2]/'web'/'static'/'review.html').read_text(encoding='utf-8')
