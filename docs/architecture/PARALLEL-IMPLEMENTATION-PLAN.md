# Build018 并行实施计划

## Track A — AI Server / Digital Brain
- 固化现有 Dify + Ollama + PostgreSQL + Weaviate 基线
- TEST/STAGING 资源盘点与健康检查
- n8n 仅在 TEST 部署
- 定义数字员工 Registry、权限、审计
- 第一批：Document Intake / Verification

## Track B — Request Platform
- FastAPI Skeleton
- Document Intake v1（SHA-256、受控复制、法人、类型）
- PostgreSQL Schema v1
- 接入 Build017 Parser/Compare
- Web Workbench

## 自研边界
只自研四法人规则、请求书核对、销售/应收状态、银行匹配、审批等公司特有逻辑。
通用能力优先复用成熟开源/免费资源。
