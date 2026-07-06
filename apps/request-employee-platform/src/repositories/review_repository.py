from datetime import datetime,timezone
from uuid import uuid4
from src.db.models import RequestCompareRunORM,ReviewTaskORM
class ReviewRepository:
 def __init__(self,db): self.db=db
 def save_compare(self,e,r):
  run=RequestCompareRunORM(id=uuid4().hex,legal_entity_id=e,request_no=r.request_no,status=str(r.status),pdf_snapshot=r.pdf.model_dump(mode='json'),excel_snapshot=r.excel.model_dump(mode='json'),difference_count=len(r.differences)); self.db.add(run); task=None
  if r.differences:
   task=ReviewTaskORM(id=uuid4().hex,legal_entity_id=e,task_type='request_compare_mismatch',business_key=r.request_no,status='open',priority='high',title_zh=f'请求书核对异常：{r.request_no}',title_ja=f'請求書照合エラー：{r.request_no}',detail_json=r.model_dump(mode='json')); self.db.add(task)
  self.db.commit(); return run,task
 def list_open(self,limit=100): return self.db.query(ReviewTaskORM).filter_by(status='open').limit(limit).all()
 def resolve(self,i,n,a=''):
  t=self.db.get(ReviewTaskORM,i)
  if not t: return None
  t.status='resolved'; t.resolution_note=n; t.assignee=a; t.resolved_at=datetime.now(timezone.utc); self.db.commit(); return t
