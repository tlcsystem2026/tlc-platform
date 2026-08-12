from pathlib import Path

from src.services.dashboard_service import DashboardService


REMOVED_TITLES = {
    "请求书处理",
    "请求书审核台",
    "客户跟踪与分析",
    "银行维护与流水格式",
    "销售数据一览",
    "应收管理",
    "银行到账核对",
    "领导审核",
}


def test_legacy_business_entries_are_removed_from_dashboard_navigator():
    summary = DashboardService().summary()
    titles = {item.title for item in summary.navigator}
    assert not REMOVED_TITLES.intersection(titles)


def test_other_dashboard_entries_remain_available():
    summary = DashboardService().summary()
    titles = {item.title for item in summary.navigator}
    assert "AI数字员工" in titles
    assert "系统健康" in titles
    assert "API文档" in titles


def test_static_core_business_shortcuts_are_removed():
    dashboard = Path(__file__).parents[1] / "src" / "web" / "static" / "dashboard.html"
    html = dashboard.read_text(encoding="utf-8")
    assert "static-business-entrances" not in html
    assert "核心业务快捷入口" not in html
