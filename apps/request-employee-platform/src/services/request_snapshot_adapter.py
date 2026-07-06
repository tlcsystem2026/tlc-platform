from decimal import Decimal,InvalidOperation
from pathlib import Path
import json,re
from src.domain.request_compare import RequestSnapshot
def money(v):
 s=str(v or '0').replace(',','').replace('￥','').replace('¥','').strip()
 try: return Decimal(s)
 except InvalidOperation:
  m=re.search(r'-?\d+(?:\.\d+)?',s); return Decimal(m.group(0)) if m else Decimal('0')
class RequestSnapshotAdapter:
 aliases={'request_no':('request_no','請求書番号','请求书编号'),'customer_name':('customer_name','顧客名','客户名称'),'request_date':('request_date','請求日','请求日期'),'currency':('currency','通貨','币种'),'subtotal':('subtotal','税抜金額','小計'),'tax_amount':('tax_amount','消費税','税額'),'total_amount':('total_amount','税込金額','合計金額')}
 def from_dict(self,data,source_type,source_document_id=''):
  def pick(n,d=''):
   for k in self.aliases[n]:
    if k in data and data[k] not in (None,''): return data[k]
   return d
  return RequestSnapshot(request_no=str(pick('request_no')),customer_name=str(pick('customer_name')),request_date=str(pick('request_date')),currency=str(pick('currency','JPY') or 'JPY'),subtotal=money(pick('subtotal',0)),tax_amount=money(pick('tax_amount',0)),total_amount=money(pick('total_amount',0)),source_document_id=source_document_id,source_type=source_type)
 def from_json_file(self,path,source_type):
  p=Path(path); return self.from_dict(json.loads(p.read_text(encoding='utf-8-sig')),source_type,str(p))
