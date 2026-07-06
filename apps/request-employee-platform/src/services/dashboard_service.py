from datetime import date
from src.core.settings import get_settings
from src.domain.dashboard import DashboardSummary,TodoItem,PerformanceMetric,NavigatorEntry
class DashboardService:
 def _open_review_count(self):
  try:
   from src.db.session import SessionLocal
   from src.db.models import ReviewTaskORM
   db=SessionLocal()
   try: return db.query(ReviewTaskORM).filter_by(status='open').count()
   finally: db.close()
  except Exception: return 0
 def _sales_total(self):
  try:
   from src.db.session import SessionLocal
   from src.db.models import SalesRecordORM
   db=SessionLocal()
   try:
    rows=db.query(SalesRecordORM).all(); return len(rows),sum(float(x.total_amount or 0) for x in rows)
   finally: db.close()
  except Exception: return 0,0
 def summary(self):
  s=get_settings(); c=self._open_review_count(); sc,sa=self._sales_total()
  return DashboardSummary(date=date.today().isoformat(),environment=s.env,todos=[TodoItem(title='待确认请求书',count=c,priority='high' if c else 'normal',href='/review'),TodoItem(title='销售数据记录',count=sc,priority='normal',href='/sales'),TodoItem(title='银行匹配候选',count=9,priority='normal',href='/dashboard#bank')],performance=[PerformanceMetric(title='待审核异常',value=str(c),unit='件',href='/review'),PerformanceMetric(title='销售记录',value=str(sc),unit='件',href='/sales'),PerformanceMetric(title='销售合计',value=f'{sa:,.0f}',unit='JPY',href='/sales')],navigator=[NavigatorEntry(title='请求书审核台',description='查看PDF/Excel核对异常并处理',href='/review',category='业务'),NavigatorEntry(title='销售数据一览',description='一致请求书登记销售，查询与统计',href='/sales',category='业务'),NavigatorEntry(title='请求书处理',description='PDF/Excel配对、解析、核对',href='/docs#/request-compare',category='业务'),NavigatorEntry(title='银行到账',description='流水导入、候选匹配、人工确认',href='/dashboard#bank',category='财务'),NavigatorEntry(title='数据库状态',description='检查数据库连接',href='/api/db/status',category='系统'),NavigatorEntry(title='API文档',description='FastAPI OpenAPI文档',href='/docs',category='系统')],alerts=[TodoItem(title='请求书核对异常',count=c,priority='high' if c else 'normal',href='/review')])
