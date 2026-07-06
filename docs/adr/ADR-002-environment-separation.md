# ADR-002 Environment Separation

Status: Accepted

TEST/STAGING 与 PROD 强制分离：数据库、文件、账号、Secret、日志、任务队列、AI权限、备份。
当前 Linux AI Server 优先定位 TEST/STAGING；PROD 上线前独立部署并通过 Go-Live Gate。
