# ADR-003 Business Navigator Dashboard First

Status: Accepted

## Decision
平台 Web 首页采用 Business Navigator Dashboard，而不是只提供技术 API 页面。

## Reason
员工与领导每天需要看到：
- 今日TODO
- AI已自动完成与待人工确认
- 销售、应收、银行到账等业绩
- 重要异常
- 各业务入口

## Scope
Build019 先提供 TEST 假数据接口和静态仪表页。
后续从 PostgreSQL、Task Center、Sales、AR、Bank、AI Runs 读取真实数据。

## Principle
业务导航页面是经营入口，不是装饰页面。
