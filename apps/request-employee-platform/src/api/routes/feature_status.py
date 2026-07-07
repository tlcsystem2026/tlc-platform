from __future__ import annotations
from html import escape
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from src.services.feature_status_service import get_guide, list_features
router = APIRouter(tags=["feature-status"])
@router.get("/api/features")
def api_list_features():
    return {"build":"Build032R4","policy":"可验收功能必须提供操作指南；入口展示必须明确标注未完成。","features":list_features()}
@router.get("/acceptance", response_class=HTMLResponse)
def acceptance_page():
    rows=[]
    for item in list_features():
        guide=f'<a href="{escape(item["guide_path"])}">操作指南</a>' if item['guide_path'] else '—'
        test_entry=f'<a href="{escape(item["test_entry"])}">测试入口</a>' if item['test_entry'] else '—'
        tag='ready' if item['status']=='可验收' else 'done' if item['status']=='已完成' else 'pending'
        rows.append('<tr>'+f'<td>{escape(item["category"])}</td><td>{escape(item["title"])}</td><td><span class="tag {tag}">{escape(item["dashboard_label"])}</span></td><td>{guide}</td><td>{test_entry}</td><td>{escape(item["completion_rule"])}</td>'+'</tr>')
    return """<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'/><title>功能进度核对表</title><style>body{font-family:Microsoft YaHei,Segoe UI,sans-serif;background:#f6f8fb;color:#111827;margin:0}header{background:linear-gradient(90deg,#172554,#2563eb);color:white;padding:22px 30px}main{max-width:1400px;margin:auto;padding:24px}.card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:18px}table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid #e5e7eb;padding:10px;text-align:left;vertical-align:top}th{background:#f8fafc}.tag{display:inline-block;border-radius:999px;padding:4px 9px;font-weight:700;font-size:12px}.ready{background:#dcfce7;color:#166534}.pending{background:#fee2e2;color:#991b1b}.done{background:#dbeafe;color:#1e40af}a{color:#2563eb;font-weight:700;text-decoration:none}.note{color:#667085;line-height:1.7}</style></head><body><header><h1>功能进度核对表</h1><p>Build032R4：可验收、未完成、操作指南分离管理</p></header><main><div class='card'><p class='note'>规则：已经提交给社长测试的功能必须提供操作指南；只是 Dashboard 入口或静态展示的功能必须标注“未完成 / 入口展示”，不能登记完成。</p><table><thead><tr><th>分类</th><th>功能</th><th>状态</th><th>操作指南</th><th>测试入口</th><th>完成登记规则</th></tr></thead><tbody>"""+''.join(rows)+"""</tbody></table></div></main></body></html>"""
@router.get("/acceptance/guide/{feature_id}", response_class=HTMLResponse)
def acceptance_guide(feature_id: str):
    data=get_guide(feature_id)
    if not data:
        raise HTTPException(status_code=404, detail='guide not found')
    f=data['feature']; g=data['guide']
    def lis(items):
        return ''.join(f'<li>{escape(x)}</li>' for x in items)
    return f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'/><title>{escape(g['title'])}</title><style>body{{font-family:Microsoft YaHei,Segoe UI,sans-serif;background:#f6f8fb;color:#111827;margin:0}}header{{background:linear-gradient(90deg,#064e3b,#059669);color:white;padding:22px 30px}}main{{max-width:1000px;margin:auto;padding:24px}}.card{{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:18px;margin:14px 0}}li{{margin:8px 0}}.tag{{display:inline-block;background:#dcfce7;color:#166534;border-radius:999px;padding:5px 10px;font-weight:700}}a{{color:#2563eb;font-weight:700;text-decoration:none}}</style></head><body><header><h1>{escape(g['title'])}</h1><p>{escape(f['dashboard_label'])}</p></header><main><div class='card'><h2>功能目的</h2><p>{escape(g['purpose'])}</p><p><span class='tag'>{escape(f['status'])}</span></p></div><div class='card'><h2>页面/API入口</h2><p>{escape(g['entry'])}</p></div><div class='card'><h2>测试前准备</h2><ol>{lis(g['preparation'])}</ol></div><div class='card'><h2>操作步骤</h2><ol>{lis(g['steps'])}</ol></div><div class='card'><h2>预期结果</h2><ol>{lis(g['expected'])}</ol></div><div class='card'><h2>验收标准</h2><p>{escape(g['acceptance'])}</p></div><p><a href='/acceptance'>返回功能进度核对表</a>　<a href='/dashboard'>返回 Dashboard</a></p></main></body></html>"""
