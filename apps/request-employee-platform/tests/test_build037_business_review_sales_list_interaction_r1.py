from pathlib import Path
R=Path("src/api/routes/request_pending_review.py").read_text(encoding="utf-8")
S=Path("src/services/request_pending_review_service.py").read_text(encoding="utf-8")
FR=Path("src/api/routes/formal_sales_ledger.py").read_text(encoding="utf-8")
FS=Path("src/services/formal_sales_ledger_service.py").read_text(encoding="utf-8")
P=Path("src/web/static/request_review_workbench.html").read_text(encoding="utf-8")
def test_unlimited_backend_contract():
 assert "Query(default=0, ge=0)" in R and "limit:int=Query(0,ge=0)" in FR
 assert 'requested_limit = int(limit or 0)' in S and 'requested_limit=int(limit or 0)' in FS
 assert '{limit_sql}' in S and '{limit_sql}' in FS
 assert P.count('qs.set("limit","0");')>=2
def test_both_tables_have_interaction_contract():
 for x in ("TLC_BUSINESS_REVIEW_SALES_LIST_INTERACTION_R1",'setup("pendingBody")','setup("salesBody")',"workbench-list-active","workbench-sortable","aria-sort","SIZE=100","部分匹配"):
  assert x in P
def test_bulk_business_rules_preserved():
 for x in ("resolveSelected('APPROVE'","noteRequiredActions","bulkNote","bulkReviewer","/bulk-resolve"):
  assert x in P
