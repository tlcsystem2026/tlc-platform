from src.db.models import LegalEntityORM
class LegalEntityRepository:
 def __init__(self,db): self.db=db
 def ensure(self,e,name=None,country='JP',language='zh'):
  obj=self.db.get(LegalEntityORM,e)
  if obj: return obj
  obj=LegalEntityORM(id=e,name=name or e,country=country,language=language); self.db.add(obj); self.db.flush(); return obj
