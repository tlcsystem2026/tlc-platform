from pathlib import Path


def test_dashboard_has_database_maintenance_entry():
    dashboard = (
        Path(__file__).parents[1] / "src/web/static/dashboard.html"
    ).read_text(encoding="utf-8")
    assert dashboard.count("/database-maintenance-center") == 1
    assert "数据库维护" in dashboard
    assert "<h2>系统运维</h2>" in dashboard
