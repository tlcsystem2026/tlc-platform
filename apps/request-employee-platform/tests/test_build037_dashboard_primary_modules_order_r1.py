from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app


ROOT = Path(__file__).parents[1]
PAGE = ROOT / "src" / "web" / "static" / "dashboard.html"
client = TestClient(app)


def test_primary_modules_are_directly_below_dashboard_title():
    page = PAGE.read_text(encoding="utf-8")

    positions = [
        page.index("<main>"),
        page.index('id="business-workflow-entrances"'),
        page.index('id="security-administration-entries"'),
        page.index('id="system-operations"'),
        page.index('id="kpis"'),
    ]

    assert positions == sorted(positions)
    assert "TLC_DASHBOARD_PRIMARY_MODULES_ORDER_R1" in page


def test_primary_modules_are_not_duplicated():
    page = PAGE.read_text(encoding="utf-8")

    assert page.count('id="business-workflow-entrances"') == 1
    assert page.count('id="security-administration-entries"') == 1
    assert page.count('id="system-operations"') == 1
    assert page.count('id="ai-support"') == 1


def test_existing_primary_links_are_preserved():
    page = PAGE.read_text(encoding="utf-8")

    required = [
        "/tlc-customer-master",
        "/tlc-bank-account-master",
        "/request-review-center",
        "/access-control-center",
        "/super-admin-management",
        "/security-ip-control-center",
        "/security-center",
        "/system-parameter-center",
        "/my-profile",
        "/database-maintenance-center",
        "/docs",
    ]

    for path in required:
        assert path in page


def test_dashboard_page_remains_available():
    response = client.get("/dashboard")

    assert response.status_code in {200, 303}