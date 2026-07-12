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
from src.api.routes.customer_reconciliation import router as customer_reconciliation_router

init_db()
app = FastAPI(title="TLC Group Request Platform", version="0.31.1-dashboard-recovery")

@app.get("/")
def root():
    return RedirectResponse(url="/dashboard")

for r in (health_router, dashboard_router, review_page_router, sales_page_router, request_compare_router, request_auto_compare_router, sales_router, db_status_router, deploy_router, system_router, ops_router, documents_router, bank_router, customer_reconciliation_router):
    app.include_router(r)
from src.api.routes.request_compare_report import router as request_compare_report_router
app.include_router(request_compare_report_router)
from src.api.routes.request_pending_review import router as request_pending_review_router
app.include_router(request_pending_review_router)
from src.api.routes.request_pending_review_resolution import router as request_pending_review_resolution_router
app.include_router(request_pending_review_resolution_router)
from src.api.routes.formal_sales_ledger import router as formal_sales_ledger_router
app.include_router(formal_sales_ledger_router)
from src.api.routes.request_review_workbench import router as request_review_workbench_router
app.include_router(request_review_workbench_router)
from src.api.routes.multi_bank_import import router as multi_bank_import_router
app.include_router(multi_bank_import_router)
from src.api.routes.bank_import_ui import router as bank_import_ui_router
app.include_router(bank_import_ui_router)
from src.api.routes.tlc_code_master import router as tlc_code_master_router
app.include_router(tlc_code_master_router)
from src.api.routes.tlc_bank_account_profile import router as tlc_bank_account_profile_router
app.include_router(tlc_bank_account_profile_router)
from src.api.routes.tlc_customer_master import router as tlc_customer_master_router
app.include_router(tlc_customer_master_router)
from src.api.routes.customer_bank_name_matching import router as customer_bank_name_matching_router
app.include_router(customer_bank_name_matching_router)
from src.api.routes.customer_period_reconciliation import router as customer_period_reconciliation_router
app.include_router(customer_period_reconciliation_router)
from src.api.routes.customer_reconciliation_history import router as customer_reconciliation_history_router
app.include_router(customer_reconciliation_history_router)
from src.api.routes.customer_reconciliation_workbench import router as customer_reconciliation_workbench_router
app.include_router(customer_reconciliation_workbench_router)
from src.api.routes.tlc_batch_center import router as tlc_batch_center_router
app.include_router(tlc_batch_center_router)
