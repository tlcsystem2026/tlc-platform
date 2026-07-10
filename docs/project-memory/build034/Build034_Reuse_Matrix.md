# Build034 Reuse Matrix

| 业务阶段 | 现有资产 | 策略 | 目标 |
|---|---|---|---|
| 原始请求书解析 | Excel/PDF Parser | 优先复用 | 输出统一RequestDocument |
| 自动比较 | `/api/requests/compare` | 兼容复用 | 输出CompareResult |
| 自动解析比较 | `/api/requests/compare-parser-json` | 兼容复用 | 接收Parser标准JSON |
| 错误处理 | 现有报告/异常结果 | 改造 | JSON/CSV错误文件 + Web详情 |
| 人工审核 | review-tasks API | 扩展 | 真实/重复/取消/通过 |
| 正式销售台账 | Sales API/DB | 扩展 | 只接收审核通过且幂等的数据 |
| 银行流水 | Bank API基础 | 扩展 | 多银行批次与标准交易 |
| 客户对账 | Customer cutoff | 复用 | 按两个截止日期进行对账与滚动 |
