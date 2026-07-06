from src.services.request_snapshot_adapter import RequestSnapshotAdapter
from src.services.request_compare_persistence_service import RequestComparePersistenceService
class RequestAutoCompareService:
 def __init__(self,db): self.db=db; self.adapter=RequestSnapshotAdapter()
 def compare_parser_json_files(self,e,pdf_json,excel_json):
  p=self.adapter.from_json_file(pdf_json,'pdf'); x=self.adapter.from_json_file(excel_json,'excel'); r=RequestComparePersistenceService(self.db).compare_and_persist(e,p,x); r['pdf_snapshot']=p.model_dump(mode='json'); r['excel_snapshot']=x.model_dump(mode='json'); return r
