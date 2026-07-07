from __future__ import annotations

import json
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.core.settings import get_settings
from src.services.export_service import export_pdf, export_xlsx

router = APIRouter(prefix="/api/customer-reconciliation", tags=["customer-reconciliation"])


PAYMENT_SOURCES = (
    "bank_transfer",
    "cash_collection",
    "special_writeoff",
    "manual_adjustment",
)


class CustomerReconciliationCutoffIn(BaseModel):
    customer_id: str = Field(..., min_length=1)
    customer_name: str = Field(..., min_length=1)
    request_date_cutoff: str
    payment_received_date_cutoff: str
    confirmed_total_amount: str = "0"
    currency: str = "JPY"
    bank_transfer_amount: str = "0"
    cash_collection_amount: str = "0"
    special_writeoff_amount: str = "0"
    manual_adjustment_amount: str = "0"
    note: str = ""
    confirmed_by: str = "system"


def _document_root() -> Path:
    settings = get_settings()
    root = getattr(settings, "document_root", None) or getattr(settings, "documents_root", None) or ""
    if not root:
        root = Path.cwd() / ".tlc-data" / "documents"
    p = Path(root)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _data_dir() -> Path:
    p = _document_root() / "customer_reconciliation"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cutoff_file() -> Path:
    return _data_dir() / "customer_cutoffs.json"


def _load_rows() -> list[dict]:
    path = _cutoff_file()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _save_rows(rows: list[dict]) -> None:
    path = _cutoff_file()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _validate_iso_date(value: str, field: str) -> None:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field} must be YYYY-MM-DD") from exc


def _to_amount_text(value: str, field: str) -> str:
    raw = str(value or "0").replace(",", "").strip()
    try:
        float(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field} must be numeric") from exc
    return raw


def _filter_rows(
    keyword: str = "",
    customer_id: str = "",
    customer_name: str = "",
    currency: str = "",
) -> list[dict]:
    rows = _load_rows()
    if keyword:
        k = keyword.lower()
        rows = [x for x in rows if k in " ".join(str(v).lower() for v in x.values())]
    if customer_id:
        rows = [x for x in rows if x.get("customer_id") == customer_id]
    if customer_name:
        rows = [x for x in rows if customer_name.lower() in x.get("customer_name", "").lower()]
    if currency:
        rows = [x for x in rows if x.get("currency") == currency]
    return sorted(rows, key=lambda x: (x.get("customer_name", ""), x.get("customer_id", "")))


def _business_scope(row: dict) -> dict:
    return {
        "customer_id": row["customer_id"],
        "customer_name": row["customer_name"],
        "next_request_condition": f"request_date > {row['request_date_cutoff']}",
        "next_payment_condition": f"payment_received_date > {row['payment_received_date_cutoff']}",
        "excluded_request_rule": f"exclude requests where request_date <= {row['request_date_cutoff']}",
        "excluded_payment_rule": f"exclude payments where payment_received_date <= {row['payment_received_date_cutoff']}",
        "payment_sources": list(PAYMENT_SOURCES),
    }


@router.get("/cutoffs")
def list_customer_cutoffs(
    keyword: str = "",
    customer_id: str = "",
    customer_name: str = "",
    currency: str = "",
):
    return _filter_rows(keyword, customer_id, customer_name, currency)


@router.post("/cutoffs")
def upsert_customer_cutoff(req: CustomerReconciliationCutoffIn):
    _validate_iso_date(req.request_date_cutoff, "request_date_cutoff")
    _validate_iso_date(req.payment_received_date_cutoff, "payment_received_date_cutoff")

    obj = {
        "customer_id": req.customer_id.strip(),
        "customer_name": req.customer_name.strip(),
        "request_date_cutoff": req.request_date_cutoff,
        "payment_received_date_cutoff": req.payment_received_date_cutoff,
        "confirmed_total_amount": _to_amount_text(req.confirmed_total_amount, "confirmed_total_amount"),
        "currency": req.currency.strip() or "JPY",
        "bank_transfer_amount": _to_amount_text(req.bank_transfer_amount, "bank_transfer_amount"),
        "cash_collection_amount": _to_amount_text(req.cash_collection_amount, "cash_collection_amount"),
        "special_writeoff_amount": _to_amount_text(req.special_writeoff_amount, "special_writeoff_amount"),
        "manual_adjustment_amount": _to_amount_text(req.manual_adjustment_amount, "manual_adjustment_amount"),
        "payment_sources": list(PAYMENT_SOURCES),
        "note": req.note,
        "confirmed_by": req.confirmed_by.strip() or "system",
        "confirmed_at": datetime.now().isoformat(timespec="seconds"),
        "status": "ready_for_next_reconciliation",
    }

    rows = _load_rows()
    replaced = False
    for idx, row in enumerate(rows):
        if row.get("customer_id") == obj["customer_id"]:
            rows[idx] = obj
            replaced = True
            break
    if not replaced:
        rows.append(obj)

    _save_rows(rows)
    result = dict(obj)
    result["next_reconciliation_scope"] = _business_scope(obj)
    return result


@router.get("/scope")
def get_next_reconciliation_scope(customer_id: str):
    rows = _filter_rows(customer_id=customer_id)
    if not rows:
        raise HTTPException(status_code=404, detail="customer reconciliation cutoff not found")
    row = rows[0]
    return _business_scope(row)


@router.get("/cutoffs/export/excel")
def export_cutoffs_excel(
    keyword: str = "",
    customer_id: str = "",
    customer_name: str = "",
    currency: str = "",
):
    return export_xlsx(_filter_rows(keyword, customer_id, customer_name, currency), "customer_reconciliation_cutoffs")


@router.get("/cutoffs/export/pdf")
def export_cutoffs_pdf(
    keyword: str = "",
    customer_id: str = "",
    customer_name: str = "",
    currency: str = "",
):
    return export_pdf(
        _filter_rows(keyword, customer_id, customer_name, currency),
        "customer_reconciliation_cutoffs",
        "Customer Reconciliation Cutoffs",
    )


@router.get("/page", response_class=HTMLResponse)
def customer_reconciliation_page():
    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>客户对账清款基准设置</title>
<style>
body{font-family:Microsoft YaHei,Segoe UI,sans-serif;background:#f6f8fb;color:#111827;margin:0}
header{background:linear-gradient(90deg,#172554,#2563eb);color:white;padding:22px 30px}
main{max-width:1360px;margin:auto;padding:22px}.card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:18px;margin:14px 0;box-shadow:0 8px 22px rgba(16,24,40,.06)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
label{display:block;color:#475467;font-size:13px;margin:8px 0 4px}input,textarea{width:100%;padding:10px;border:1px solid #d0d5dd;border-radius:10px;box-sizing:border-box}
textarea{min-height:72px}button{border:0;border-radius:10px;padding:10px 14px;background:#2563eb;color:white;font-weight:700;margin:4px;cursor:pointer}.secondary{background:#475467}.ok{background:#059669}
table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid #e5e7eb;padding:9px;text-align:left;vertical-align:top}th{background:#f8fafc}.desc{color:#667085;font-size:13px;line-height:1.7}
.tag{display:inline-block;border-radius:999px;padding:4px 9px;background:#dcfce7;color:#166534;font-weight:700;font-size:12px}
.warn{display:inline-block;border-radius:999px;padding:4px 9px;background:#fee2e2;color:#991b1b;font-weight:700;font-size:12px}
pre{white-space:pre-wrap;background:#101828;color:#d1fadf;padding:12px;border-radius:10px;max-height:360px;overflow:auto}
</style>
</head>
<body>
<header><h1>客户对账清款基准设置</h1><p>实际业务功能：按客户设置请求日截至日与银行到账日截至日，作为下次对账排除基准。</p></header>
<main>
<section class="card">
<h2>业务说明</h2>
<p class="desc">针对一个客户，确认截止某个请求日以前的请求书合计已经收款完毕；同时截止某个银行到账日以前的入金记录也已经处理完毕。收款来源包括所有银行进账、本公司现金收款、特别核销、手工调整和备注。下次对账时，不再包含该客户请求日截至日及以前的请求书，也不再包含银行到账日截至日及以前的入金/核销记录。</p>
<p><span class="tag">可验收 / 待社长测试</span> <span class="warn">不是按银行账户设置</span></p>
</section>

<section class="card">
<h2>保存客户清款基准</h2>
<div class="grid">
<div><label>客户 ID</label><input id="customer_id" value="CUST-TEST-001"/></div>
<div><label>客户名称</label><input id="customer_name" value="测试客户"/></div>
<div><label>请求日截至日</label><input id="request_date_cutoff" type="date"/></div>
<div><label>银行到账日截至日</label><input id="payment_received_date_cutoff" type="date"/></div>
<div><label>确认已收款合计</label><input id="confirmed_total_amount" value="0"/></div>
<div><label>币种</label><input id="currency" value="JPY"/></div>
<div><label>银行进账金额</label><input id="bank_transfer_amount" value="0"/></div>
<div><label>现金收款金额</label><input id="cash_collection_amount" value="0"/></div>
<div><label>特别核销金额</label><input id="special_writeoff_amount" value="0"/></div>
<div><label>手工调整金额</label><input id="manual_adjustment_amount" value="0"/></div>
<div><label>确认人</label><input id="confirmed_by" value="社长测试"/></div>
</div>
<label>特别核销 / 现金收款 / 手工调整备注</label>
<textarea id="note" placeholder="例如：现金收款由本公司某日入账；差额经社长确认特别核销。"></textarea>
<button class="ok" onclick="saveCutoff()">保存基准</button>
<button class="secondary" onclick="loadCutoffs()">重新读取</button>
<pre id="result" style="display:none"></pre>
</section>

<section class="card">
<h2>检索与导出</h2>
<div class="grid">
<div><label>关键词</label><input id="keyword" placeholder="客户名/备注/金额"/></div>
<div><label>客户 ID</label><input id="filter_customer_id"/></div>
<div><label>客户名称</label><input id="filter_customer_name"/></div>
<div><label>币种</label><input id="filter_currency"/></div>
</div>
<button onclick="loadCutoffs()">检索</button>
<button class="secondary" onclick="resetFilters()">重置</button>
<button onclick="exportFile('excel')">导出 Excel</button>
<button onclick="exportFile('pdf')">导出 PDF</button>
<table>
<thead><tr><th>客户</th><th>请求日截至</th><th>银行到账日截至</th><th>确认合计</th><th>银行进账</th><th>现金</th><th>特别核销</th><th>调整</th><th>确认人/时间</th><th>备注</th></tr></thead>
<tbody id="rows"></tbody>
</table>
</section>
</main>
<script>
function today(){return new Date().toISOString().slice(0,10)}
request_date_cutoff.value=today(); payment_received_date_cutoff.value=today();
function params(){return new URLSearchParams({keyword:keyword.value,customer_id:filter_customer_id.value,customer_name:filter_customer_name.value,currency:filter_currency.value}).toString()}
function show(obj){result.style.display='block';result.textContent=JSON.stringify(obj,null,2)}
async function saveCutoff(){
 const body={customer_id:customer_id.value,customer_name:customer_name.value,request_date_cutoff:request_date_cutoff.value,payment_received_date_cutoff:payment_received_date_cutoff.value,confirmed_total_amount:confirmed_total_amount.value,currency:currency.value,bank_transfer_amount:bank_transfer_amount.value,cash_collection_amount:cash_collection_amount.value,special_writeoff_amount:special_writeoff_amount.value,manual_adjustment_amount:manual_adjustment_amount.value,note:note.value,confirmed_by:confirmed_by.value};
 const r=await fetch('/api/customer-reconciliation/cutoffs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const j=await r.json(); show(j); filter_customer_id.value=body.customer_id; await loadCutoffs();
}
async function loadCutoffs(){
 const r=await fetch('/api/customer-reconciliation/cutoffs?'+params()); const d=await r.json();
 rows.innerHTML=d.map(x=>`<tr><td><b>${x.customer_name}</b><br>${x.customer_id}</td><td>${x.request_date_cutoff}</td><td>${x.payment_received_date_cutoff}</td><td>${x.confirmed_total_amount} ${x.currency}</td><td>${x.bank_transfer_amount}</td><td>${x.cash_collection_amount}</td><td>${x.special_writeoff_amount}</td><td>${x.manual_adjustment_amount}</td><td>${x.confirmed_by}<br>${x.confirmed_at}</td><td>${x.note||''}</td></tr>`).join('');
}
function resetFilters(){keyword.value='';filter_customer_id.value='';filter_customer_name.value='';filter_currency.value='';loadCutoffs()}
function exportFile(type){location.href='/api/customer-reconciliation/cutoffs/export/'+type+'?'+params()}
loadCutoffs();
</script>
</body></html>"""
