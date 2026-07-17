from datetime import date
from src.core.settings import get_settings
from src.domain.dashboard import DashboardSummary, TodoItem, PerformanceMetric, NavigatorEntry

class DashboardService:
    def _open_review_count(self):
        try:
            from src.db.session import SessionLocal
            from src.db.models import ReviewTaskORM
            db = SessionLocal()
            try:
                return db.query(ReviewTaskORM).filter_by(status="open").count()
            finally:
                db.close()
        except Exception:
            return 0

    def _request_wait_review_count(self):
        try:
            from sqlalchemy import text
            from src.db.session import SessionLocal

            db = SessionLocal()
            try:
                table_exists = db.execute(
                    text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' "
                        "AND name='tlc_request_review_queue'"
                    )
                ).first()
                if not table_exists:
                    return 0
                row = db.execute(
                    text(
                        "SELECT COUNT(*) AS count "
                        "FROM tlc_request_review_queue "
                        "WHERE review_status = 'WAIT_REVIEW'"
                    )
                ).first()
                return int(row._mapping["count"]) if row else 0
            finally:
                db.close()
        except Exception:
            return 0

    def _sales_total(self):
        try:
            from src.db.session import SessionLocal
            from src.db.models import SalesRecordORM
            db = SessionLocal()
            try:
                rows = db.query(SalesRecordORM).all()
                return len(rows), sum(float(x.total_amount or 0) for x in rows)
            finally:
                db.close()
        except Exception:
            return 0, 0

    def summary(self):
        s = get_settings()
        review_count = self._open_review_count()
        request_wait_review_count = self._request_wait_review_count()
        sales_count, sales_amount = self._sales_total()
        return DashboardSummary(
            date=date.today().isoformat(),
            environment=s.env,
            todos=[
                TodoItem(title="待核对请求书", count=request_wait_review_count, priority="high" if request_wait_review_count else "normal", href="/request-review-center"),
                TodoItem(title="核对异常待处理", count=review_count, priority="high" if review_count else "normal", href="/review"),
                TodoItem(title="待进入销售数据", count=3, priority="high", href="/sales"),
                TodoItem(title="待领导审批", count=0, priority="normal", href="/review"),
                TodoItem(title="今日到期应收", count=5, priority="high", href="/dashboard#ar"),
                TodoItem(title="银行匹配候选", count=9, priority="normal", href="/dashboard#bank"),
                TodoItem(title="AI数字员工待确认", count=review_count, priority="normal", href="/dashboard#digital-employees"),
            ],
            performance=[
                PerformanceMetric(title="今日请求书处理", value="24", unit="件", trend="+8", href="/dashboard#requests"),
                PerformanceMetric(title="核对一致率", value="96.2", unit="%", trend="+1.5%", href="/dashboard#requests"),
                PerformanceMetric(title="待审核异常", value=str(review_count), unit="件", trend="", href="/review"),
                PerformanceMetric(title="销售记录", value=str(sales_count), unit="件", trend="", href="/sales"),
                PerformanceMetric(title="销售合计", value=f"{sales_amount:,.0f}", unit="JPY", trend="", href="/sales"),
                PerformanceMetric(title="已到账金额", value="860,000", unit="JPY", trend="", href="/dashboard#bank"),
                PerformanceMetric(title="未匹配到账", value="4", unit="件", trend="-1", href="/dashboard#bank"),
                PerformanceMetric(title="逾期应收", value="11", unit="件", trend="-2", href="/dashboard#ar"),
            ],
            navigator=[
                NavigatorEntry(title="请求书处理", description="PDF/Excel配对、解析、核对、差异处理", href="/docs#/request-compare", category="业务"),
                NavigatorEntry(title="请求书审核台", description="查看PDF/Excel核对异常并进行处理", href="/review", category="业务"),
                NavigatorEntry(title="客户跟踪与分析", description="客户维护、CSV导入导出、别名设置", href="/tlc-customer-master", category="业务"),
                NavigatorEntry(title="银行维护与流水格式", description="银行、银行账户／口座、流水 Adapter 与文件编码关联", href="/tlc-bank-account-master", category="业务"),
                NavigatorEntry(title="销售数据一览", description="一致请求书登记销售，查询与统计", href="/sales", category="业务"),
                NavigatorEntry(title="应收管理", description="到期、逾期、部分到账、催办", href="/dashboard#ar", category="财务"),
                NavigatorEntry(title="银行到账核对", description="流水导入、候选匹配、人工确认", href="/dashboard#bank", category="财务"),
                NavigatorEntry(title="原始文件管理", description="请求书、Excel、银行流水、版本与Hash", href="/dashboard#documents", category="文件"),
                NavigatorEntry(title="AI数字员工", description="自动处理记录、置信度、异常与人工接管", href="/dashboard#digital-employees", category="AI"),
                NavigatorEntry(title="AI业务支持", description="知识库、Tools、模型服务、业务问答", href="/dashboard#ai-support", category="AI"),
                NavigatorEntry(title="领导审核", description="高金额、低置信、跨法人、例外审批", href="/review", category="管理"),
                NavigatorEntry(title="系统健康", description="API、数据库、AI服务、任务状态", href="/health", category="系统"),
                NavigatorEntry(title="数据库状态", description="检查SQLite/PostgreSQL连接", href="/api/db/status", category="系统"),
                NavigatorEntry(title="API文档", description="FastAPI OpenAPI文档", href="/docs", category="系统"),
            ],
            alerts=[
                TodoItem(title="请求书核对异常", count=review_count, priority="high" if review_count else "normal", href="/review"),
                TodoItem(title="低置信银行匹配需要确认", count=4, priority="high", href="/dashboard#bank"),
                TodoItem(title="超过30天未到账", count=3, priority="critical", href="/dashboard#ar"),
            ],
        )
