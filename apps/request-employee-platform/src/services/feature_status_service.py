from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Literal
FeatureStatus = Literal["未完成", "开发中", "可验收", "已完成", "返修中"]
@dataclass(frozen=True)
class FeatureItem:
    id: str
    title: str
    status: FeatureStatus
    category: str
    dashboard_label: str
    is_entry_only: bool
    testable: bool
    guide_path: str
    test_entry: str
    completion_rule: str
    note: str
FEATURES = [
    FeatureItem("sales_search_export", "销售一览检索与 Excel/PDF 导出", "可验收", "销售/请求书关联", "可验收 / 待社长测试", False, True, "/acceptance/guide/sales_search_export", "/sales", "社长使用正式数据完成检索、Excel 导出、PDF 导出并回复 OK 后，登记为已完成。", "Build032R2 已提交。PDF 为基础版，正式中日文字体排版在里程碑版优化。"),
    FeatureItem("bank_reconciliation_cutoff", "银行对账：上次清款截至日设置", "可验收", "财务/银行对账", "可验收 / 待社长测试", False, True, "/acceptance/guide/bank_reconciliation_cutoff", "/api/bank/reconciliation/settings", "社长使用实际法人和银行账户保存截至日，并确认本次开始日自动计算正确后，登记为已完成。", "Build032R3 已提交。当前先提供 API 验收，正式画面在后续 Build 接入。"),
    FeatureItem("bank_reconciliation_page", "银行对账正式画面", "未完成", "财务/银行对账", "未完成 / 入口展示", True, False, "", "", "正式页面、检索、保存、导出闭环完成后才可提交验收。", "目前不能标记完成，Dashboard 只允许显示为未完成。"),
    FeatureItem("bank_statement_import", "银行流水导入", "未完成", "财务/银行对账", "未完成 / 入口展示", True, False, "", "", "支持正式流水文件导入、校验、错误提示后才可提交验收。", "未开发。"),
    FeatureItem("bank_auto_matching", "银行自动匹配", "未完成", "财务/银行对账", "未完成 / 入口展示", True, False, "", "", "正式数据匹配、未匹配处理、人工确认完成后才可提交验收。", "未开发。"),
    FeatureItem("digital_employee_coordination", "数字员工协调", "未完成", "AI/数字员工", "未完成 / 参考入口", True, False, "", "", "请求书平台完成业务派工和结果回写后才可提交验收。", "目前只是未来参考，不计入完成。"),
]
GUIDES = {
    "sales_search_export": {
        "title": "销售一览检索与导出：操作指南",
        "purpose": "确认销售一览可以按照正式数据进行检索，并且只导出当前检索结果。",
        "entry": "浏览器打开 /sales；API 可使用 /api/sales、/api/sales/export/excel、/api/sales/export/pdf。",
        "preparation": ["确认 API 服务已启动在 http://127.0.0.1:8018。", "准备至少一条销售数据，包含法人、请求书号、客户名、销售日期、金额、状态。"],
        "steps": ["打开 /sales 或使用 API 查询 /api/sales。", "按关键词、法人、状态、日期范围、金额范围进行检索。", "点击或访问 Excel 导出接口，确认生成 .xlsx 文件。", "点击或访问 PDF 导出接口，确认生成 .pdf 文件。", "确认导出的内容与当前检索条件一致，不是全量误导出。"],
        "expected": ["检索结果只显示符合条件的数据。", "Excel 文件可以被 Excel 打开。", "PDF 文件可以打开。", "导出数据与检索结果一致。"],
        "acceptance": "社长使用正式数据测试 OK 后，回复：销售一览检索与导出 OK。",
    },
    "bank_reconciliation_cutoff": {
        "title": "银行对账上次清款截至日：操作指南",
        "purpose": "确认系统能按法人和银行账户保存上次对账清款截至日，并自动计算本次对账开始日。",
        "entry": "API：/api/bank/reconciliation/settings；期间确认：/api/bank/reconciliation/period。",
        "preparation": ["确认 API 服务已启动在 http://127.0.0.1:8018。", "准备实际法人编号、银行账户编号、银行名称、上次清款截至日。"],
        "steps": ["POST /api/bank/reconciliation/settings，提交 legal_entity_id、bank_account_id、bank_name、last_reconciled_date。", "确认返回 last_reconciled_date 与输入一致。", "确认 current_start_date = last_reconciled_date + 1 日。", "GET /api/bank/reconciliation/settings 按法人和账户查询，确认数据已保存。", "GET /api/bank/reconciliation/period 确认本次对账期间。"],
        "expected": ["同一法人 + 银行账户再次保存时覆盖旧设置，不产生重复主记录。", "上次清款截至日当天视为已清款，本次从次日开始。", "设置可以被导出为 Excel/PDF。"],
        "acceptance": "社长使用实际法人和银行账户测试 OK 后，回复：银行对账清款截至日 OK。",
    },
}
def list_features():
    return [asdict(x) for x in FEATURES]
def get_feature(feature_id: str):
    for item in FEATURES:
        if item.id == feature_id:
            return asdict(item)
    return None
def get_guide(feature_id: str):
    f = get_feature(feature_id)
    g = GUIDES.get(feature_id)
    if not f or not g:
        return None
    return {"feature": f, "guide": g}
