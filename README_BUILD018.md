# TLC BUILD018 — Parallel Start

本包启动两条并行主线：
A. AI Server / Digital Brain / Digital Workforce
B. Request / Sales / AR / Bank Platform

本次可执行增量：
- FastAPI TEST skeleton
- `/health`
- Document Intake v1：SHA-256、受控复制、法人/文档类型元数据
- TEST PostgreSQL compose
- Windows 本地 venv 启动脚本（venv 不放 NAS）
- ADR-001 开源/免费资源优先
- ADR-002 TEST/PROD 强制分离
- 两个 pytest

## Windows TEST
1. 将包覆盖到 Repository 根目录（同名文件以后包覆盖前包）
2. 复制 `.env.example` 为 `.env` 并修改 TEST 路径
3. 执行 `scripts\run-test-api-local.ps1`

API: http://127.0.0.1:8018
Docs: http://127.0.0.1:8018/docs

注意：本包只启动 TEST 能力，不连接 PROD。
