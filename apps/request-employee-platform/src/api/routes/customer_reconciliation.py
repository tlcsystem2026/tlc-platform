
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

router = APIRouter(prefix='/api/customer-reconciliation', tags=['customer-reconciliation'])
PAYMENT_SOURCES = ('bank_transfer','cash_collection','special_writeoff','manual_adjustment')
STATUS_VALUES = ('draft','ready_to_confirm','confirmed','special_confirmed','cancelled')

class CustomerReconciliationCutoffIn(BaseModel):
    customer_id: str = Field(..., min_length=1)
    customer_name: str = Field(..., min_length=1)
    request_date_cutoff: str
    bank_received_date_cutoff: str
    request_total_amount: str = '0'
    bank_receipt_amount: str = '0'
    cash_receipt_amount: str = '0'
    special_writeoff_amount: str = '0'
    manual_adjustment_amount: str = '0'
    currency: str = 'JPY'
    status: str = 'confirmed'
    special_confirm_reason: str = ''
    note: str = ''
    confirmed_by: str = 'system'

def _root() -> Path:
    s = get_settings()
    base = getattr(s, 'document_root', None) or getattr(s, 'documents_root', None) or ''
    if not base:
        base = Path.cwd() / '.tlc-data' / 'documents'
    p = Path(base) / 'customer_reconciliation'
    p.mkdir(parents=True, exist_ok=True)
    return p

def _active_file() -> Path: return _root() / 'customer_cutoffs.json'
def _history_file() -> Path: return _root() / 'customer_cutoff_history.json'

def _load(path: Path) -> list[dict]:
    if not path.exists(): return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []

def _save(path: Path, rows: list[dict]) -> None:
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)

def _d(v: str, field: str) -> str:
    try: return date.fromisoformat(v).isoformat()
    except ValueError as exc: raise HTTPException(status_code=400, detail=f'{field} must be YYYY-MM-DD') from exc

def _a(v: str, field: str) -> str:
    raw = str(v or '0').replace(',', '').strip()
    try: return str(Decimal(raw))
    except InvalidOperation as exc: raise HTTPException(status_code=400, detail=f'{field} must be numeric') from exc

def _dec(row: dict, key: str) -> Decimal: return Decimal(str(row.get(key, '0') or '0'))
def _balance(row: dict) -> Decimal:
    return _dec(row,'request_total_amount') - _dec(row,'bank_receipt_amount') - _dec(row,'cash_receipt_amount') - _dec(row,'special_writeoff_amount') - _dec(row,'manual_adjustment_amount')

def _scope(row: dict) -> dict:
    return {
        'customer_id': row['customer_id'],
        'customer_name': row['customer_name'],
        'next_request_condition': f"request_date > {row['request_date_cutoff']}",
        'next_bank_receipt_condition': f"bank_received_date > {row['bank_received_date_cutoff']}",
        'excluded_request_rule': f"exclude requests where request_date <= {row['request_date_cutoff']}",
        'excluded_bank_receipt_rule': f"exclude bank receipts assigned to this customer where bank_received_date <= {row['bank_received_date_cutoff']}",
        'non_bank_sources_rule': 'cash_collection, special_writeoff and manual_adjustment are controlled by their own record status and whether they were included in this confirmation',
        'payment_sources': list(PAYMENT_SOURCES),
    }

def _search(keyword='', customer_id='', customer_name='', status='', currency='', confirmed_by='', request_date_from='', request_date_to='', bank_received_date_from='', bank_received_date_to='') -> list[dict]:
    rows = _load(_active_file())
    if customer_id: rows = [x for x in rows if x.get('customer_id') == customer_id]
    if customer_name: rows = [x for x in rows if customer_name.lower() in x.get('customer_name','').lower()]
    if status: rows = [x for x in rows if x.get('status') == status]
    if currency: rows = [x for x in rows if x.get('currency') == currency]
    if confirmed_by: rows = [x for x in rows if confirmed_by.lower() in x.get('confirmed_by','').lower()]
    if request_date_from: rows = [x for x in rows if x.get('request_date_cutoff','') >= request_date_from]
    if request_date_to: rows = [x for x in rows if x.get('request_date_cutoff','') <= request_date_to]
    if bank_received_date_from: rows = [x for x in rows if x.get('bank_received_date_cutoff','') >= bank_received_date_from]
    if bank_received_date_to: rows = [x for x in rows if x.get('bank_received_date_cutoff','') <= bank_received_date_to]
    if keyword:
        k = keyword.lower()
        rows = [x for x in rows if k in ' '.join(str(v).lower() for v in x.values())]
    return sorted(rows, key=lambda x: (x.get('customer_name',''), x.get('customer_id','')))

@router.get('/cutoffs')
def list_customer_cutoffs(keyword: str='', customer_id: str='', customer_name: str='', status: str='', currency: str='', confirmed_by: str='', request_date_from: str='', request_date_to: str='', bank_received_date_from: str='', bank_received_date_to: str=''):
    return _search(keyword, customer_id, customer_name, status, currency, confirmed_by, request_date_from, request_date_to, bank_received_date_from, bank_received_date_to)

@router.post('/cutoffs')
def upsert_customer_cutoff(req: CustomerReconciliationCutoffIn):
    if req.status not in STATUS_VALUES:
        raise HTTPException(status_code=400, detail=f'status must be one of {STATUS_VALUES}')
    obj = {
        'customer_id': req.customer_id.strip(), 'customer_name': req.customer_name.strip(),
        'request_date_cutoff': _d(req.request_date_cutoff, 'request_date_cutoff'),
        'bank_received_date_cutoff': _d(req.bank_received_date_cutoff, 'bank_received_date_cutoff'),
        'request_total_amount': _a(req.request_total_amount, 'request_total_amount'),
        'bank_receipt_amount': _a(req.bank_receipt_amount, 'bank_receipt_amount'),
        'cash_receipt_amount': _a(req.cash_receipt_amount, 'cash_receipt_amount'),
        'special_writeoff_amount': _a(req.special_writeoff_amount, 'special_writeoff_amount'),
        'manual_adjustment_amount': _a(req.manual_adjustment_amount, 'manual_adjustment_amount'),
        'currency': req.currency.strip() or 'JPY', 'status': req.status,
        'special_confirm_reason': req.special_confirm_reason.strip(), 'note': req.note,
        'confirmed_by': req.confirmed_by.strip() or 'system', 'confirmed_at': datetime.now().isoformat(timespec='seconds'),
        'payment_sources': list(PAYMENT_SOURCES),
    }
    bal = _balance(obj)
    obj['balance_amount'] = str(bal)
    if bal != 0 and obj['status'] != 'special_confirmed':
        raise HTTPException(status_code=400, detail='balance_amount is not zero. Use status=special_confirmed with special_confirm_reason to confirm specially.')
    if obj['status'] == 'special_confirmed' and not obj['special_confirm_reason']:
        raise HTTPException(status_code=400, detail='special_confirm_reason is required for special_confirmed')
    rows = _load(_active_file())
    old = None
    for i, row in enumerate(rows):
        if row.get('customer_id') == obj['customer_id']:
            old = row; rows[i] = obj; break
    else:
        rows.append(obj)
    _save(_active_file(), rows)
    hist = _load(_history_file())
    hist.append({'event':'upsert','customer_id':obj['customer_id'],'changed_at':obj['confirmed_at'],'changed_by':obj['confirmed_by'],'old':old,'new':obj})
    _save(_history_file(), hist)
    result = dict(obj)
    result['next_reconciliation_scope'] = _scope(obj)
    return result

@router.get('/scope')
def get_next_reconciliation_scope(customer_id: str):
    rows = _search(customer_id=customer_id)
    if not rows: raise HTTPException(status_code=404, detail='customer reconciliation cutoff not found')
    return _scope(rows[0])

@router.get('/history')
def list_history(customer_id: str=''):
    rows = _load(_history_file())
    return [x for x in rows if x.get('customer_id') == customer_id] if customer_id else rows

@router.get('/cutoffs/export/excel')
def export_cutoffs_excel(keyword: str='', customer_id: str='', customer_name: str='', status: str='', currency: str='', confirmed_by: str='', request_date_from: str='', request_date_to: str='', bank_received_date_from: str='', bank_received_date_to: str=''):
    return export_xlsx(list_customer_cutoffs(keyword, customer_id, customer_name, status, currency, confirmed_by, request_date_from, request_date_to, bank_received_date_from, bank_received_date_to), 'customer_reconciliation_cutoffs')

@router.get('/cutoffs/export/pdf')
def export_cutoffs_pdf(keyword: str='', customer_id: str='', customer_name: str='', status: str='', currency: str='', confirmed_by: str='', request_date_from: str='', request_date_to: str='', bank_received_date_from: str='', bank_received_date_to: str=''):
    return export_pdf(list_customer_cutoffs(keyword, customer_id, customer_name, status, currency, confirmed_by, request_date_from, request_date_to, bank_received_date_from, bank_received_date_to), 'customer_reconciliation_cutoffs', 'Customer Reconciliation Cutoffs')

@router.get('/page', response_class=HTMLResponse)
def customer_reconciliation_page():
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>客户对账清款基准设置</title><style>body{font-family:Microsoft YaHei,Segoe UI,sans-serif;background:#f6f8fb;color:#111827;margin:0}header{background:linear-gradient(90deg,#172554,#2563eb);color:white;padding:22px 30px}main{max-width:1400px;margin:auto;padding:22px}.card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:18px;margin:14px 0;box-shadow:0 8px 22px rgba(16,24,40,.06)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}label{display:block;color:#475467;font-size:13px;margin:8px 0 4px}input,select,textarea{width:100%;padding:10px;border:1px solid #d0d5dd;border-radius:10px;box-sizing:border-box}textarea{min-height:70px}button{border:0;border-radius:10px;padding:10px 14px;background:#2563eb;color:white;font-weight:700;margin:4px;cursor:pointer}.secondary{background:#475467}.ok{background:#059669}table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid #e5e7eb;padding:9px;text-align:left;vertical-align:top}th{background:#f8fafc}.desc{color:#667085;font-size:13px;line-height:1.7}.tag{display:inline-block;border-radius:999px;padding:4px 9px;background:#dcfce7;color:#166534;font-weight:700;font-size:12px}.warn{display:inline-block;border-radius:999px;padding:4px 9px;background:#fee2e2;color:#991b1b;font-weight:700;font-size:12px}pre{white-space:pre-wrap;background:#101828;color:#d1fadf;padding:12px;border-radius:10px;max-height:320px;overflow:auto}</style></head><body><header><h1>客户对账清款基准设置</h1><p>按客户设置请求日截至日与银行到账日截至日。不是按银行账户设置。</p></header><main><section class="card"><h2>业务说明</h2><p class="desc">针对一个客户，确认截止某个请求日以前的请求书合计已经收款完毕；同时截止某个银行到账日以前的已归属该客户的银行入金也处理完毕。收款完成来源包括银行进账、现金收款、特别核销、人工调整。下次对账不再包含这些历史边界内的数据。</p><span class="tag">可验收 / 待社长测试</span> <span class="warn">两个日期独立</span></section><section class="card"><h2>严格匹配 + 全数据模糊检索</h2><p class="desc">本页面支持客户ID、状态、日期范围等严格匹配查询，同时支持 keyword 全数据范围模糊检索。保存和检索功能通过下方 API 表单执行。</p><div class="grid"><div><label>客户ID</label><input id="customer_id" value="CUST-TEST-001"/></div><div><label>客户名称</label><input id="customer_name" value="测试客户"/></div><div><label>请求日截至日</label><input id="request_date_cutoff" type="date"/></div><div><label>银行到账日截至日</label><input id="bank_received_date_cutoff" type="date"/></div><div><label>请求书合计</label><input id="request_total_amount" value="0"/></div><div><label>银行进账合计</label><input id="bank_receipt_amount" value="0"/></div><div><label>现金收款合计</label><input id="cash_receipt_amount" value="0"/></div><div><label>特别核销合计</label><input id="special_writeoff_amount" value="0"/></div><div><label>人工调整合计</label><input id="manual_adjustment_amount" value="0"/></div><div><label>状态</label><select id="status"><option value="confirmed">已确认</option><option value="special_confirmed">特别确认</option><option value="draft">草稿</option></select></div></div><label>特别确认原因</label><input id="special_confirm_reason"/><label>备注</label><textarea id="note"></textarea><button class="ok" onclick="saveCutoff()">保存/确认</button><button onclick="loadCutoffs()">检索</button><button onclick="exportFile('excel')">导出Excel</button><button onclick="exportFile('pdf')">导出PDF</button><pre id="result"></pre><table><tbody id="rows"></tbody></table></section></main><script>function today(){return new Date().toISOString().slice(0,10)} request_date_cutoff.value=today(); bank_received_date_cutoff.value=today();function show(x){result.textContent=JSON.stringify(x,null,2)}async function saveCutoff(){const body={customer_id:customer_id.value,customer_name:customer_name.value,request_date_cutoff:request_date_cutoff.value,bank_received_date_cutoff:bank_received_date_cutoff.value,request_total_amount:request_total_amount.value,bank_receipt_amount:bank_receipt_amount.value,cash_receipt_amount:cash_receipt_amount.value,special_writeoff_amount:special_writeoff_amount.value,manual_adjustment_amount:manual_adjustment_amount.value,status:status.value,special_confirm_reason:special_confirm_reason.value,note:note.value,confirmed_by:'社长测试'}; const r=await fetch('/api/customer-reconciliation/cutoffs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); show(await r.json()); await loadCutoffs()}async function loadCutoffs(){const r=await fetch('/api/customer-reconciliation/cutoffs'); const d=await r.json(); rows.innerHTML=d.map(x=>`<tr><td>${x.customer_id}</td><td>${x.customer_name}</td><td>${x.request_date_cutoff}</td><td>${x.bank_received_date_cutoff}</td><td>${x.balance_amount}</td></tr>`).join('')}function exportFile(t){location.href='/api/customer-reconciliation/cutoffs/export/'+t}loadCutoffs();</script></body></html>'''
