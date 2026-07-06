from decimal import Decimal
from src.domain.request_compare import CompareDifference,CompareStatus,RequestCompareResult,RequestSnapshot
class RequestCompareService:
 def compare(self,pdf:RequestSnapshot,excel:RequestSnapshot):
  d=[]
  def add(f,a,b,z,j): d.append(CompareDifference(field=f,pdf_value=str(a),excel_value=str(b),message_zh=z,message_ja=j))
  norm=lambda x: ''.join(str(x or '').replace('\u3000',' ').upper().split())
  if norm(pdf.request_no)!=norm(excel.request_no): add('request_no',pdf.request_no,excel.request_no,'请求书编号不一致','請求書番号が一致しません')
  if norm(pdf.customer_name)!=norm(excel.customer_name): add('customer_name',pdf.customer_name,excel.customer_name,'客户名称不一致','顧客名が一致しません')
  for f in ('subtotal','tax_amount','total_amount'):
   a,b=Decimal(getattr(pdf,f)),Decimal(getattr(excel,f))
   if a!=b: add(f,a,b,f'{f} 金额不一致',f'{f} 金額が一致しません')
  return RequestCompareResult(request_no=pdf.request_no or excel.request_no,status=CompareStatus.MATCHED if not d else CompareStatus.MISMATCHED,differences=d,pdf=pdf,excel=excel)
