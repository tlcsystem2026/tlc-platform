from pathlib import Path
P=Path("src/web/static/request_review_center.html")
def test_two_review_lists_have_shared_interaction():
 t=P.read_text(encoding="utf-8")
 for x in ("TLC_REQUEST_REVIEW_LIST_INTERACTION_R1",'document.getElementById("batchQueue")','document.getElementById("reviewRows")',"review-list-active","review-list-sortable","aria-sort","SIZE=100","部分匹配","全部关键字段"):
  assert x in t
def test_checkbox_clicks_do_not_activate_rows():
 t=P.read_text(encoding="utf-8").split("TLC_REQUEST_REVIEW_LIST_INTERACTION_R1",1)[1]
 assert 'e.target.closest("input,button,a,select")' in t
 assert "scrollTo(" not in t
