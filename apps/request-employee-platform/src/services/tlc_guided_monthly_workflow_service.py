from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


STEPS = [
    {"code":"MASTER_SETUP","name":"系统参数与基础主数据","path":"/system-parameter-center","description":"确认请求书目录、银行目录、客户 Master、银行与账户设置。"},
    {"code":"FILE_REVIEW","name":"请求书导入 Batch 与文件核对","path":"/request-review-center","description":"执行 PDF／Excel 批量核对，处理文件名、年月、格式和文件间一致性。"},
    {"code":"BUSINESS_REVIEW","name":"请求书业务审核","path":"/requests/review-workbench","description":"审核金额、重复、取消、现收等业务内容；通过后自动登记正式销售台账。"},
    {"code":"SALES_LEDGER","name":"正式销售与统计","path":"/sales","description":"确认正式销售台账，并按月份、客户和税率查看销售统计。"},
    {"code":"BANK_IMPORT","name":"银行流水导入","path":"/bank-import","description":"按银行账户导入真实流水，检查日期、金额、重复数据和原始文件。"},
    {"code":"CUSTOMER_MATCHING","name":"银行流水客户匹配","path":"/customer-recommended-matching-center","description":"执行客户名称、自动及推荐匹配，人工确认未匹配或歧义记录。"},
    {"code":"RECONCILIATION","name":"客户销售与入金对账","path":"/customer-payment-reconciliation","description":"核对销售、入金和差额，并在客户对账工作台完成确认与结转。"},
    {"code":"MONTHLY_CLOSE","name":"月结检查与签核","path":"/monthly-close-center","description":"完成异常检查、对账确认、月结授权、签核及跨月结转。"},
]


def _table_exists(db:Session,name:str)->bool:
    return db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),{"name":name}).first() is not None


def _columns(db:Session,name:str)->set[str]:
    return {str(row[1]) for row in db.execute(text(f"PRAGMA table_info({name})")).all()} if _table_exists(db,name) else set()


def _count(db:Session,table:str,where:str="",params:dict[str,Any]|None=None)->int:
    if not _table_exists(db,table):return 0
    return int(db.execute(text(f"SELECT COUNT(*) FROM {table} {where}"),params or {}).scalar() or 0)


def _month_values(value:str)->tuple[str,str]:
    raw=str(value or "").strip().replace("/","-")
    if len(raw)==6 and raw.isdigit():return raw[:4]+"-"+raw[4:],raw
    if len(raw)>=7:return raw[:7],raw[:7].replace("-","")
    current=date.today().strftime("%Y-%m")
    return current,current.replace("-","")


def _latest_month(db:Session)->str:
    for table in ("tlc_request_batch_compare","request_pending_review"):
        if _table_exists(db,table) and "business_month" in _columns(db,table):
            row=db.execute(text(f"SELECT business_month FROM {table} WHERE COALESCE(business_month,'')<>'' ORDER BY rowid DESC LIMIT 1")).first()
            if row:return str(row[0] or "")
    return date.today().strftime("%Y-%m")


def _latest_request_batch(db:Session,compact_month:str)->dict[str,Any]:
    if not _table_exists(db,"tlc_request_batch_compare"):return {}
    row=db.execute(text("""SELECT * FROM tlc_request_batch_compare
      WHERE REPLACE(business_month,'-','')=:month
      ORDER BY COALESCE(is_current,0) DESC,rowid DESC LIMIT 1"""),{"month":compact_month}).first()
    return dict(row._mapping) if row else {}


def guided_monthly_workflow(db:Session,*,business_month:str="")->dict[str,Any]:
    display_month,compact_month=_month_values(business_month or _latest_month(db))
    month_prefix=display_month+"%";params={"month":compact_month,"prefix":month_prefix}

    customer_count=_count(db,"tlc_customer_master")
    bank_account_count=_count(db,"tlc_bank_account_profile")
    batch=_latest_request_batch(db,compact_month)
    batch_id=str(batch.get("id") or "")
    file_review_count=_count(db,"tlc_request_review_queue","WHERE REPLACE(business_month,'-','')=:month AND COALESCE(is_current,1)=1",params) if "is_current" in _columns(db,"tlc_request_review_queue") else _count(db,"tlc_request_review_queue","WHERE REPLACE(business_month,'-','')=:month",params)
    file_exception_count=int(batch.get("exception_count") or 0)+int(batch.get("error_count") or 0)

    business_total=_count(db,"request_pending_review","WHERE REPLACE(business_month,'-','')=:month",params)
    business_pending=_count(db,"request_pending_review","WHERE REPLACE(business_month,'-','')=:month AND status='PENDING_REVIEW'",params)
    business_problem=_count(db,"request_pending_review","WHERE REPLACE(business_month,'-','')=:month AND status IN ('REJECTED','CANCELLED','DUPLICATE','AMOUNT_CORRECTION_REQUIRED','BUSINESS_CORRECTION_REQUIRED','ON_HOLD')",params)

    sales_count=0
    if _table_exists(db,"formal_sales_request_ledger"):
        if _table_exists(db,"request_pending_review"):
            sales_count=int(db.execute(text("""SELECT COUNT(*) FROM formal_sales_request_ledger l
              LEFT JOIN request_pending_review p ON p.id=l.pending_review_id
              WHERE l.status='ACTIVE' AND (REPLACE(p.business_month,'-','')=:month OR (COALESCE(p.business_month,'')='' AND l.request_date LIKE :prefix))"""),params).scalar() or 0)
        else:sales_count=_count(db,"formal_sales_request_ledger","WHERE status='ACTIVE' AND request_date LIKE :prefix",params)

    bank_transaction_count=_count(db,"bank_transaction_import","WHERE transaction_date LIKE :prefix",params)
    name_match_count=_count(db,"tlc_customer_name_match_result","WHERE match_status IN ('MATCHED','OVERRIDDEN')")
    auto_match_count=_count(db,"tlc_customer_auto_match","WHERE status='MATCHED'")
    accepted_match_count=_count(db,"tlc_customer_recommended_match","WHERE status='ACCEPTED'")
    matching_count=name_match_count+auto_match_count+accepted_match_count

    snapshot_count=_count(db,"tlc_customer_reconciliation_snapshot","WHERE created_at LIKE :prefix",params)
    confirmed_reconciliation_count=_count(db,"tlc_customer_reconciliation_confirmation","WHERE status='CONFIRMED' AND confirmed_at LIKE :prefix",params)

    signoff_status=""
    if _table_exists(db,"tlc_monthly_close_signoff"):
        row=db.execute(text("SELECT status FROM tlc_monthly_close_signoff WHERE REPLACE(business_month,'-','')=:month ORDER BY rowid DESC LIMIT 1"),params).first()
        signoff_status=str(row[0] or "") if row else ""

    state={
      "MASTER_SETUP":("DONE" if customer_count and bank_account_count else "PENDING",f"客户={customer_count}，银行账户={bank_account_count}"),
      "FILE_REVIEW":("DONE" if batch_id and file_review_count and file_exception_count==0 else ("ATTENTION" if file_exception_count else "PENDING"),f"当前 Batch={batch_id or '无'}，文件 Review={file_review_count}，异常={file_exception_count}"),
      "BUSINESS_REVIEW":("DONE" if business_total and business_pending==0 and business_problem==0 else ("ATTENTION" if business_problem else "PENDING"),f"业务审核总数={business_total}，待审核={business_pending}，需处理={business_problem}"),
      "SALES_LEDGER":("DONE" if sales_count and business_pending==0 else "PENDING",f"正式销售={sales_count}"),
      "BANK_IMPORT":("DONE" if bank_transaction_count else "PENDING",f"本月银行流水={bank_transaction_count}"),
      "CUSTOMER_MATCHING":("DONE" if bank_transaction_count and matching_count else "PENDING",f"已确认匹配={matching_count}"),
      "RECONCILIATION":("DONE" if confirmed_reconciliation_count else ("PENDING" if snapshot_count==0 else "IN_PROGRESS"),f"对账快照={snapshot_count}，已确认={confirmed_reconciliation_count}"),
      "MONTHLY_CLOSE":("DONE" if signoff_status=="APPROVED" else "PENDING",f"月结签核={signoff_status or '未开始'}"),
    }

    steps=[];recommended=False
    for index,base in enumerate(STEPS,1):
        status,detail=state[base["code"]];item={**base,"order":index,"status":status,"detail":detail,"recommended":False}
        if not recommended and status!="DONE":item["recommended"]=True;recommended=True
        steps.append(item)
    done=sum(1 for item in steps if item["status"]=="DONE")
    alerts=[]
    if file_exception_count:alerts.append({"severity":"HIGH","code":"FILE_REVIEW_EXCEPTION","message":f"文件核对仍有 {file_exception_count} 件异常","target":"/request-review-center"})
    if business_pending:alerts.append({"severity":"MEDIUM","code":"BUSINESS_REVIEW_PENDING","message":f"仍有 {business_pending} 件请求书待业务审核","target":"/requests/review-workbench"})
    if business_problem:alerts.append({"severity":"HIGH","code":"BUSINESS_REVIEW_ATTENTION","message":f"仍有 {business_problem} 件业务审核需要处理","target":"/requests/review-workbench"})
    if bank_transaction_count and not matching_count:alerts.append({"severity":"MEDIUM","code":"BANK_MATCHING_PENDING","message":"银行流水已导入，但尚未完成客户匹配","target":"/customer-recommended-matching-center"})
    return {"business_month":display_month,"completed_step_count":done,"total_step_count":len(steps),"progress_percent":round(done*100/len(steps)),"next_step_code":next((x["code"] for x in steps if x["recommended"]),""),"all_complete":done==len(steps),"steps":steps,"alerts":alerts}
