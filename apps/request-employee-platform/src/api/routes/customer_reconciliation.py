
from __future__ import annotations
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from src.core.settings import get_settings
from src.services.export_service import export_pdf, export_xlsx

router=APIRouter(prefix="/api/customer-reconciliation",tags=["customer-reconciliation"])
PAYMENT_SOURCES=("bank_transfer","cash_collection","special_writeoff","manual_adjustment")
STATUS_VALUES=("draft","ready_to_confirm","confirmed","special_confirmed","cancelled")
I18N={
"zh":{"title":"客户对账清款基准设置","customer_id":"客户ID","customer_name":"客户名称","request_cutoff":"请求日截至日","bank_cutoff":"银行到账日截至日","request_total":"请求书合计","bank":"银行进账","cash":"现金收款","writeoff":"特别核销","adjustment":"人工调整","balance":"差额","status":"状态","confirmed_by":"确认人","confirmed_at":"确认时间","note":"备注","action":"操作","edit":"编辑","exported_at":"导出时间","filters":"检索条件","total":"合计"},
"ja":{"title":"顧客照合・消込基準設定","customer_id":"顧客ID","customer_name":"顧客名","request_cutoff":"請求日締切日","bank_cutoff":"銀行入金日締切日","request_total":"請求合計","bank":"銀行入金","cash":"現金入金","writeoff":"特別消込","adjustment":"手動調整","balance":"差額","status":"ステータス","confirmed_by":"確認者","confirmed_at":"確認日時","note":"備考","action":"操作","edit":"編集","exported_at":"出力日時","filters":"検索条件","total":"合計"},
"en":{"title":"Customer Reconciliation Cutoff","customer_id":"Customer ID","customer_name":"Customer Name","request_cutoff":"Request Date Cutoff","bank_cutoff":"Bank Received Date Cutoff","request_total":"Request Total","bank":"Bank Receipt","cash":"Cash Receipt","writeoff":"Special Write-off","adjustment":"Manual Adjustment","balance":"Balance","status":"Status","confirmed_by":"Confirmed By","confirmed_at":"Confirmed At","note":"Note","action":"Action","edit":"Edit","exported_at":"Exported At","filters":"Filters","total":"Total"}}
FIELDS=["customer_id","customer_name","request_date_cutoff","bank_received_date_cutoff","request_total_amount","bank_receipt_amount","cash_receipt_amount","special_writeoff_amount","manual_adjustment_amount","balance_amount","status","confirmed_by","confirmed_at","note"]
LABEL_KEYS=["customer_id","customer_name","request_cutoff","bank_cutoff","request_total","bank","cash","writeoff","adjustment","balance","status","confirmed_by","confirmed_at","note"]

class CustomerReconciliationCutoffIn(BaseModel):
    customer_id:str=Field(...,min_length=1)
    customer_name:str=Field(...,min_length=1)
    request_date_cutoff:str
    bank_received_date_cutoff:str
    request_total_amount:str="0"
    bank_receipt_amount:str="0"
    cash_receipt_amount:str="0"
    special_writeoff_amount:str="0"
    manual_adjustment_amount:str="0"
    currency:str="JPY"
    status:str="confirmed"
    special_confirm_reason:str=""
    note:str=""
    confirmed_by:str="system"
    change_reason:str=""

def _document_root()->Path:
    settings=get_settings()
    root=getattr(settings,"document_root",None) or getattr(settings,"documents_root",None) or ""
    if not root: root=Path.cwd()/".tlc-data"/"documents"
    path=Path(root)/"customer_reconciliation"; path.mkdir(parents=True,exist_ok=True); return path
def _active_file()->Path: return _document_root()/"customer_cutoffs.json"
def _history_file()->Path: return _document_root()/"customer_cutoff_history.json"
def _load(path:Path)->list[dict]:
    if not path.exists(): return []
    try:
        data=json.loads(path.read_text(encoding="utf-8")); return data if isinstance(data,list) else []
    except json.JSONDecodeError: return []
def _save(path:Path, rows:list[dict])->None:
    tmp=path.with_suffix(path.suffix+".tmp"); tmp.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8"); tmp.replace(path)
def _date(value:str, field:str)->str:
    try: return date.fromisoformat(value).isoformat()
    except ValueError as exc: raise HTTPException(status_code=400,detail=f"{field} must be YYYY-MM-DD") from exc
def _amount(value:str, field:str)->Decimal:
    try: return Decimal(str(value or "0").replace(",","").strip())
    except InvalidOperation as exc: raise HTTPException(status_code=400,detail=f"{field} must be numeric") from exc
def _scope(row:dict)->dict:
    return {"customer_id":row["customer_id"],"customer_name":row["customer_name"],"next_request_condition":f"request_date > {row['request_date_cutoff']}","next_bank_receipt_condition":f"bank_received_date > {row['bank_received_date_cutoff']}","excluded_request_rule":f"exclude requests where request_date <= {row['request_date_cutoff']}","excluded_bank_receipt_rule":f"exclude bank receipts assigned to this customer where bank_received_date <= {row['bank_received_date_cutoff']}","non_bank_sources_rule":"cash_collection, special_writeoff and manual_adjustment are controlled by their own record status and whether they were included in this confirmation","payment_sources":list(PAYMENT_SOURCES)}
def _search(keyword:str="",customer_id:str="",customer_name:str="",status:str="",currency:str="",confirmed_by:str="",request_date_from:str="",request_date_to:str="",bank_received_date_from:str="",bank_received_date_to:str="")->list[dict]:
    rows=_load(_active_file())
    if customer_id: rows=[x for x in rows if x.get("customer_id")==customer_id]
    if customer_name: rows=[x for x in rows if x.get("customer_name")==customer_name]
    if status: rows=[x for x in rows if x.get("status")==status]
    if currency: rows=[x for x in rows if x.get("currency")==currency]
    if confirmed_by: rows=[x for x in rows if x.get("confirmed_by")==confirmed_by]
    if request_date_from: rows=[x for x in rows if x.get("request_date_cutoff","")>=request_date_from]
    if request_date_to: rows=[x for x in rows if x.get("request_date_cutoff","")<=request_date_to]
    if bank_received_date_from: rows=[x for x in rows if x.get("bank_received_date_cutoff","")>=bank_received_date_from]
    if bank_received_date_to: rows=[x for x in rows if x.get("bank_received_date_cutoff","")<=bank_received_date_to]
    if keyword:
        k=keyword.casefold(); rows=[x for x in rows if k in " ".join(str(v) for v in x.values()).casefold()]
    return sorted(rows,key=lambda x:(x.get("customer_name",""),x.get("customer_id","")))

@router.get("/cutoffs")
def list_customer_cutoffs(keyword:str="",customer_id:str="",customer_name:str="",status:str="",currency:str="",confirmed_by:str="",request_date_from:str="",request_date_to:str="",bank_received_date_from:str="",bank_received_date_to:str=""):
    return _search(keyword,customer_id,customer_name,status,currency,confirmed_by,request_date_from,request_date_to,bank_received_date_from,bank_received_date_to)
@router.get("/cutoffs/{customer_id}")
def get_customer_cutoff(customer_id:str):
    rows=_search(customer_id=customer_id)
    if not rows: raise HTTPException(status_code=404,detail="customer reconciliation cutoff not found")
    return rows[0]
@router.post("/cutoffs")
def upsert_customer_cutoff(req:CustomerReconciliationCutoffIn):
    if req.status not in STATUS_VALUES: raise HTTPException(status_code=400,detail=f"status must be one of {STATUS_VALUES}")
    obj=req.model_dump() if hasattr(req,"model_dump") else req.dict()
    obj["customer_id"]=obj["customer_id"].strip(); obj["customer_name"]=obj["customer_name"].strip()
    obj["request_date_cutoff"]=_date(obj["request_date_cutoff"],"request_date_cutoff")
    obj["bank_received_date_cutoff"]=_date(obj["bank_received_date_cutoff"],"bank_received_date_cutoff")
    for f in ("request_total_amount","bank_receipt_amount","cash_receipt_amount","special_writeoff_amount","manual_adjustment_amount"): obj[f]=str(_amount(obj[f],f))
    bal=_amount(obj["request_total_amount"],"request_total_amount")-_amount(obj["bank_receipt_amount"],"bank_receipt_amount")-_amount(obj["cash_receipt_amount"],"cash_receipt_amount")-_amount(obj["special_writeoff_amount"],"special_writeoff_amount")-_amount(obj["manual_adjustment_amount"],"manual_adjustment_amount")
    obj["balance_amount"]=str(bal); obj["payment_sources"]=list(PAYMENT_SOURCES); obj["confirmed_by"]=obj["confirmed_by"].strip() or "system"; obj["confirmed_at"]=datetime.now().isoformat(timespec="seconds")
    if bal!=0 and obj["status"]!="special_confirmed": raise HTTPException(status_code=400,detail="balance_amount is not zero. Use status=special_confirmed with special_confirm_reason to confirm specially.")
    if obj["status"]=="special_confirmed" and not obj["special_confirm_reason"].strip(): raise HTTPException(status_code=400,detail="special_confirm_reason is required for special_confirmed")
    rows=_load(_active_file()); old=None
    for i,row in enumerate(rows):
        if row.get("customer_id")==obj["customer_id"]: old=row; rows[i]=obj; break
    else: rows.append(obj)
    _save(_active_file(),rows)
    hist=_load(_history_file()); hist.append({"event":"update" if old else "create","customer_id":obj["customer_id"],"changed_at":obj["confirmed_at"],"changed_by":obj["confirmed_by"],"change_reason":obj.get("change_reason",""),"old":old,"new":obj}); _save(_history_file(),hist)
    res=dict(obj); res["next_reconciliation_scope"]=_scope(obj); return res
@router.get("/scope")
def get_next_reconciliation_scope(customer_id:str):
    rows=_search(customer_id=customer_id)
    if not rows: raise HTTPException(status_code=404,detail="customer reconciliation cutoff not found")
    return _scope(rows[0])
@router.get("/history")
def list_history(customer_id:str=""):
    rows=_load(_history_file()); return [x for x in rows if not customer_id or x.get("customer_id")==customer_id]
def _translated_rows(rows:list[dict], lang:str)->list[dict]:
    tr=I18N.get(lang,I18N["zh"]); labels=[tr[k] for k in LABEL_KEYS]
    return [{label:row.get(field,"") for label,field in zip(labels,FIELDS)} for row in rows]
def _export_rows(rows:list[dict], lang:str, filters:dict)->list[dict]:
    tr=I18N.get(lang,I18N["zh"]); data=[{tr["title"]:tr["title"],tr["exported_at"]:datetime.now().isoformat(timespec="seconds"),tr["filters"]:"; ".join(f"{k}={v}" for k,v in filters.items() if v) or "-"}]; data.extend(_translated_rows(rows,lang))
    data.append({tr["customer_id"]:tr["total"],tr["request_total"]:str(sum((_amount(x.get("request_total_amount","0"),"request_total_amount") for x in rows),Decimal("0"))),tr["bank"]:str(sum((_amount(x.get("bank_receipt_amount","0"),"bank_receipt_amount") for x in rows),Decimal("0"))),tr["cash"]:str(sum((_amount(x.get("cash_receipt_amount","0"),"cash_receipt_amount") for x in rows),Decimal("0"))),tr["writeoff"]:str(sum((_amount(x.get("special_writeoff_amount","0"),"special_writeoff_amount") for x in rows),Decimal("0"))),tr["adjustment"]:str(sum((_amount(x.get("manual_adjustment_amount","0"),"manual_adjustment_amount") for x in rows),Decimal("0"))),tr["balance"]:str(sum((_amount(x.get("balance_amount","0"),"balance_amount") for x in rows),Decimal("0")))})
    return data
@router.get("/cutoffs/export/excel")
def export_cutoffs_excel(lang:str="zh",keyword:str="",customer_id:str="",customer_name:str="",status:str="",currency:str="",confirmed_by:str="",request_date_from:str="",request_date_to:str="",bank_received_date_from:str="",bank_received_date_to:str=""):
    filters={k:v for k,v in locals().items() if k!="lang"}; rows=_search(**filters); return export_xlsx(_export_rows(rows,lang,filters),"customer_reconciliation_cutoffs")
@router.get("/cutoffs/export/pdf")
def export_cutoffs_pdf(lang:str="zh",keyword:str="",customer_id:str="",customer_name:str="",status:str="",currency:str="",confirmed_by:str="",request_date_from:str="",request_date_to:str="",bank_received_date_from:str="",bank_received_date_to:str=""):
    filters={k:v for k,v in locals().items() if k!="lang"}; rows=_search(**filters); return export_pdf(_export_rows(rows,lang,filters),"customer_reconciliation_cutoffs",I18N.get(lang,I18N["zh"])["title"])

PAGE_HTML = r"""
<!doctype html>
<html><head><meta charset="utf-8"><title>Customer Reconciliation</title>
<style>body{font-family:Arial,"Microsoft YaHei",sans-serif;background:#f6f8fb;margin:0}header{background:#1d4ed8;color:#fff;padding:18px}main{padding:16px;max-width:1500px;margin:auto}.card{background:#fff;padding:14px;margin:12px 0;border-radius:10px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:8px}input,select,textarea{width:100%;box-sizing:border-box;padding:7px}button{padding:8px 11px;margin:3px;background:#2563eb;color:#fff;border:0;border-radius:6px}table{width:100%;border-collapse:collapse;font-size:12px}th,td{border:1px solid #ddd;padding:6px}th{background:#eef2ff}.scroll{overflow:auto;max-height:520px}</style></head><body>
<header><h1 id="title"></h1><p>不是按银行账户设置 / Not bank-account based / 銀行口座単位ではありません</p><select id="lang" onchange="renderLang()"><option value="zh">中文</option><option value="ja">日本語</option><option value="en">English</option></select></header>
<main><section class="card"><h2 id="formTitle"></h2><p>严格匹配查询 + 全数据模糊检索</p><div class="grid">
<div><label data-i="customer_id"></label><input id="customer_id"></div><div><label data-i="customer_name"></label><input id="customer_name"></div><div><label data-i="request_cutoff"></label><input id="request_date_cutoff" type="date"></div><div><label data-i="bank_cutoff"></label><input id="bank_received_date_cutoff" type="date"></div><div><label data-i="request_total"></label><input id="request_total_amount" value="0"></div><div><label data-i="bank"></label><input id="bank_receipt_amount" value="0"></div><div><label data-i="cash"></label><input id="cash_receipt_amount" value="0"></div><div><label data-i="writeoff"></label><input id="special_writeoff_amount" value="0"></div><div><label data-i="adjustment"></label><input id="manual_adjustment_amount" value="0"></div><div><label>Currency</label><input id="currency" value="JPY"></div><div><label data-i="status"></label><select id="status"><option value="confirmed">confirmed</option><option value="special_confirmed">special_confirmed</option><option value="draft">draft</option></select></div><div><label data-i="confirmed_by"></label><input id="confirmed_by"></div></div>
<label>Special confirm reason</label><input id="special_confirm_reason"><label data-i="note"></label><textarea id="note"></textarea><label>Change reason</label><input id="change_reason"><button onclick="save()">Save / Update</button><button onclick="clearForm()">New</button><pre id="msg"></pre></section>
<section class="card"><h2>Search</h2><div class="grid"><div><label>Keyword (all fields fuzzy)</label><input id="keyword"></div><div><label>Customer ID (exact)</label><input id="f_customer_id"></div><div><label>Customer Name (exact)</label><input id="f_customer_name"></div><div><label>Status (exact)</label><input id="f_status"></div><div><label>Currency (exact)</label><input id="f_currency"></div><div><label>Confirmed By (exact)</label><input id="f_confirmed_by"></div><div><label>Request from</label><input id="request_date_from" type="date"></div><div><label>Request to</label><input id="request_date_to" type="date"></div><div><label>Bank received from</label><input id="bank_received_date_from" type="date"></div><div><label>Bank received to</label><input id="bank_received_date_to" type="date"></div></div><button onclick="load()">Search</button><button onclick="resetSearch()">Reset</button><button onclick="exp('excel')">Excel</button><button onclick="exp('pdf')">PDF</button><div class="scroll"><table><thead><tr id="headers"></tr></thead><tbody id="rows"></tbody></table></div></section></main>
<script>
const T={zh:{title:"客户对账清款基准设置",customer_id:"客户ID",customer_name:"客户名称",request_cutoff:"请求日截至日",bank_cutoff:"银行到账日截至日",request_total:"请求书合计",bank:"银行进账",cash:"现金收款",writeoff:"特别核销",adjustment:"人工调整",balance:"差额",status:"状态",confirmed_by:"确认人",confirmed_at:"确认时间",note:"备注",action:"操作",edit:"编辑"},ja:{title:"顧客照合・消込基準設定",customer_id:"顧客ID",customer_name:"顧客名",request_cutoff:"請求日締切日",bank_cutoff:"銀行入金日締切日",request_total:"請求合計",bank:"銀行入金",cash:"現金入金",writeoff:"特別消込",adjustment:"手動調整",balance:"差額",status:"ステータス",confirmed_by:"確認者",confirmed_at:"確認日時",note:"備考",action:"操作",edit:"編集"},en:{title:"Customer Reconciliation Cutoff",customer_id:"Customer ID",customer_name:"Customer Name",request_cutoff:"Request Date Cutoff",bank_cutoff:"Bank Received Date Cutoff",request_total:"Request Total",bank:"Bank Receipt",cash:"Cash Receipt",writeoff:"Special Write-off",adjustment:"Manual Adjustment",balance:"Balance",status:"Status",confirmed_by:"Confirmed By",confirmed_at:"Confirmed At",note:"Note",action:"Action",edit:"Edit"}};
const keys=["customer_id","customer_name","request_cutoff","bank_cutoff","request_total","bank","cash","writeoff","adjustment","balance","status","confirmed_by","confirmed_at","note","action"];const fields=["customer_id","customer_name","request_date_cutoff","bank_received_date_cutoff","request_total_amount","bank_receipt_amount","cash_receipt_amount","special_writeoff_amount","manual_adjustment_amount","balance_amount","status","confirmed_by","confirmed_at","note"];let data=[];
function renderLang(){let t=T[lang.value];title.textContent=t.title;formTitle.textContent=t.title;document.querySelectorAll("[data-i]").forEach(x=>x.textContent=t[x.dataset.i]);headers.innerHTML=keys.map(k=>`<th>${t[k]}</th>`).join("");renderRows()}
function qs(){return new URLSearchParams({keyword:keyword.value,customer_id:f_customer_id.value,customer_name:f_customer_name.value,status:f_status.value,currency:f_currency.value,confirmed_by:f_confirmed_by.value,request_date_from:request_date_from.value,request_date_to:request_date_to.value,bank_received_date_from:bank_received_date_from.value,bank_received_date_to:bank_received_date_to.value})}
async function load(){let r=await fetch("/api/customer-reconciliation/cutoffs?"+qs());data=await r.json();renderRows()}
function renderRows(){let t=T[lang.value];rows.innerHTML=data.map((x,i)=>`<tr><td>${fields.map(f=>x[f]??"").join("</td><td>")}</td><td><button onclick="editRow(${i})">${t.edit}</button></td></tr>`).join("")}
function editRow(i){let x=data[i];["customer_id","customer_name","request_date_cutoff","bank_received_date_cutoff","request_total_amount","bank_receipt_amount","cash_receipt_amount","special_writeoff_amount","manual_adjustment_amount","currency","status","special_confirm_reason","note","confirmed_by","change_reason"].forEach(f=>{let e=document.getElementById(f);if(e)e.value=x[f]??""});customer_id.readOnly=true;scrollTo(0,0)}
function clearForm(){customer_id.readOnly=false;["customer_id","customer_name","special_confirm_reason","note","change_reason"].forEach(f=>document.getElementById(f).value="")}
async function save(){let fs=["customer_id","customer_name","request_date_cutoff","bank_received_date_cutoff","request_total_amount","bank_receipt_amount","cash_receipt_amount","special_writeoff_amount","manual_adjustment_amount","currency","status","special_confirm_reason","note","confirmed_by","change_reason"],body={};fs.forEach(f=>body[f]=document.getElementById(f).value);let r=await fetch("/api/customer-reconciliation/cutoffs",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});let j=await r.json();msg.textContent=JSON.stringify(j,null,2);if(r.ok)await load()}
function resetSearch(){["keyword","f_customer_id","f_customer_name","f_status","f_currency","f_confirmed_by","request_date_from","request_date_to","bank_received_date_from","bank_received_date_to"].forEach(f=>document.getElementById(f).value="");load()}
function exp(t){let q=qs();q.set("lang",lang.value);location.href="/api/customer-reconciliation/cutoffs/export/"+t+"?"+q}
renderLang();load();
</script></body></html>
"""
@router.get("/page",response_class=HTMLResponse)
def customer_reconciliation_page():
    return PAGE_HTML
