from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from src.db.init_db import init_db
from src.api.routes.health import router as health_router
from src.api.routes.dashboard import router as dashboard_router
from src.api.routes.review_page import router as review_page_router
from src.api.routes.sales_page import router as sales_page_router
from src.api.routes.request_compare import router as request_compare_router
from src.api.routes.request_auto_compare import router as request_auto_compare_router
from src.api.routes.sales import router as sales_router
from src.api.routes.db_status import router as db_status_router
from src.api.routes.deploy import router as deploy_router
from src.api.routes.system import router as system_router
from src.api.routes.ops import router as ops_router
from src.api.routes.documents import router as documents_router
from src.api.routes.bank import router as bank_router

init_db()
app = FastAPI(title="TLC Group Request Platform", version="0.31.1-dashboard-recovery")

@app.get("/")
def root():
    return RedirectResponse(url="/dashboard")

for r in (health_router, dashboard_router, review_page_router, sales_page_router, request_compare_router, request_auto_compare_router, sales_router, db_status_router, deploy_router, system_router, ops_router, documents_router, bank_router):
    app.include_router(r)
