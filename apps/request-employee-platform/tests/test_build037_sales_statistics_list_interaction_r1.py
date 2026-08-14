from pathlib import Path
P=Path("src/web/static/sales.html").read_text(encoding="utf-8")
def test_sales_list_interaction_contract():
 for x in ("TLC_SALES_STATISTICS_LIST_INTERACTION_R1","sales-stat-row-active","sales-stat-sortable","aria-sort","SIZE=100","salesStatSearch","salesStatField","salesStatPageInfo","部分匹配"):
  assert x in P
def test_sales_existing_data_contract_preserved():
 for x in ("document.querySelectorAll(\"table\")","querySelector(\"tbody\")"):
  assert x in P
def test_selection_does_not_interfere_with_controls():
 x=P.split("TLC_SALES_STATISTICS_LIST_INTERACTION_R1",1)[1]
 assert 'e.target.closest("input,button,a,select")' in x and "scrollTo(" not in x
