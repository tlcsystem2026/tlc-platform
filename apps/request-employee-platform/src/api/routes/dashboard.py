from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from src.services.dashboard_service import DashboardService
router=APIRouter(tags=['dashboard'])
@router.get('/api/dashboard/summary')
def summary(): return DashboardService().summary().model_dump(mode='json')
@router.get('/dashboard',response_class=HTMLResponse)
def page(): return (Path(__file__).parents[2]/'web'/'static'/'dashboard.html').read_text(encoding='utf-8')
