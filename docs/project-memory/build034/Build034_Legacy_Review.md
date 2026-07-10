# Build034 M0 — Legacy Review

## 结论

Build034 不推倒重来。当前系统已经暴露出以下可延续能力：

- `POST /api/requests/compare`：现有请求书比较入口。
- `POST /api/requests/compare-parser-json`：现有自动解析比较入口。
- `GET /api/requests/review-tasks` 与 resolve API：现有审核任务基础。
- Sales API 与数据库登记基础：可作为正式销售台账的演进起点。
- Bank reconciliation API 基础：可作为银行导入与客户对账的后续入口。

## 初步复用矩阵

| 能力 | 处理策略 | Build034动作 |
|---|---|---|
| Excel Parser | Reuse / Refactor | 先定位真实源码和现有测试，再封装标准结构 |
| PDF Parser | Reuse / Refactor | 保留现有解析成果，补字段来源与错误信息 |
| Excel/PDF Compare | Reuse / Refactor | 统一差异模型，保留旧API兼容 |
| Compare API | Reuse | 作为新工作流入口之一 |
| Parser JSON Compare | Reuse | 作为自动比较入口 |
| Review Tasks | Refactor | 扩展真实性、重复、取消和审批状态 |
| Error Report | Refactor / Rewrite | 保留机器结果，新增错误文件和Web详情 |
| Sales DB/API | Refactor | 扩展为审核后正式销售请求书台账 |
| Bank API | Refactor | 等银行样本后建立多银行导入Adapter |
| Image Import | Interface only | Build034仅定义接口，不做OCR实现 |

## 风险

M0尚未获得GitHub仓库完整源码快照，因此“Reuse/Refactor/Rewrite”是基于当前可见API与历史WBS的初步判断。M1-T01必须以GitHub main真实文件和测试为依据做文件级确认，不允许直接重写。
