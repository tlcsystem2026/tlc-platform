from pathlib import Path
R=Path("src/api/routes/tlc_customer_candidate.py").read_text(encoding="utf-8");S=Path("src/services/tlc_customer_candidate_service.py").read_text(encoding="utf-8");P=Path("src/web/static/customer_import_candidate_center.html").read_text(encoding="utf-8")
def test_unlimited_contract():
 assert "Query(0, ge=0)" in R and "limit: int = 0" in S and "requested_limit > 0" in S and "{limit_sql}" in S and "limit:'0'" in P
def test_candidate_list_contract():
 for x in ("TLC_CUSTOMER_CANDIDATE_LIST_INTERACTION_R1","candidate-active","candidate-sortable","aria-sort","SIZE=100","candidateSearch","candidateField","部分匹配"):
  assert x in P
def test_candidate_business_functions_preserved():
 for x in ("bulkAction('LINK_EXISTING')","bulkAction('CREATE_NEW')","exportCsv()","importCsv()","formal-name-input"):
  assert x in P
