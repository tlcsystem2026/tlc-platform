from src.repositories.legal_entity_repository import LegalEntityRepository
from src.repositories.review_repository import ReviewRepository
from src.services.request_compare_service import RequestCompareService
class RequestComparePersistenceService:
 def __init__(self,db): self.db=db
 def compare_and_persist(self,e,pdf,excel):
  LegalEntityRepository(self.db).ensure(e); r=RequestCompareService().compare(pdf,excel); run,task=ReviewRepository(self.db).save_compare(e,r)
  return {'compare_run_id':run.id,'status':str(r.status),'difference_count':len(r.differences),'differences':[x.model_dump(mode='json') for x in r.differences],'review_task_id':task.id if task else None}
