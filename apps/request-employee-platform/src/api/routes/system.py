from fastapi import APIRouter
from src.core.settings import get_settings

router = APIRouter(prefix="/api/system", tags=["system"])

@router.get("/runtime")
def runtime():
    s = get_settings()
    return {
        "environment": s.env,
        "version": "0.31.1-dashboard-recovery",
        "dashboard": "/dashboard",
        "review": "/review",
        "sales": "/sales",
        "docs": "/docs",
        "db_status": "/api/db/status",
        "dashboard_contract": "rich-business-navigator-with-static-fallback-digital-employees-and-deploy",
    }
