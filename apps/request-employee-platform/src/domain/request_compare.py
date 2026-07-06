from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, Field
class CompareStatus(StrEnum): MATCHED='matched'; MISMATCHED='mismatched'; NEEDS_REVIEW='needs_review'
class RequestSnapshot(BaseModel):
    request_no:str; customer_name:str=''; request_date:str=''; currency:str='JPY'; subtotal:Decimal=Decimal('0'); tax_amount:Decimal=Decimal('0'); total_amount:Decimal=Decimal('0'); source_document_id:str=''; source_type:str=''
class CompareDifference(BaseModel): field:str; pdf_value:str=''; excel_value:str=''; severity:str='error'; message_zh:str=''; message_ja:str=''
class RequestCompareResult(BaseModel): request_no:str; status:CompareStatus; differences:list[CompareDifference]=Field(default_factory=list); pdf:RequestSnapshot; excel:RequestSnapshot
