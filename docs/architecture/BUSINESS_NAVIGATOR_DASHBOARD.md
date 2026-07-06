# Business Navigator Dashboard

## 目标
员工每天打开系统后，第一眼看到今天该处理什么、经营状态如何、异常在哪里、各业务入口在哪里。

## 一期模块
- 今日TODO
- 业绩KPI
- 重要异常
- 业务入口
- 系统健康入口

## 后续数据来源
- tasks
- approvals
- requests
- sales
- receivables
- bank_transactions
- payment_matches
- ai_runs
- audit_logs

## 页面路径
- `/dashboard`
- `/api/dashboard/summary`

## 后续演进
1. 接入Task Center
2. 接入Sales/AR/Bank真实统计
3. 按用户角色显示入口
4. 按法人过滤数据
5. 社长驾驶舱独立化
