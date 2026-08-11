from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from src.services.tlc_global_dashboard_navigation_service import (
    MARKER,
    inject_dashboard_link,
    install_global_dashboard_navigation,
)


ROOT = Path(__file__).parents[1]


def test_injects_single_global_dashboard_link():
    source = "<!doctype html><html><body><h1>Page</h1></body></html>"
    result = inject_dashboard_link(source, "/customer-import-candidate-center")
    assert MARKER in result
    assert result.count('href="/dashboard"') == 1
    assert "&#36820;&#22238; Dashboard" in result
    assert result.index(MARKER) < result.index("</body>")


def test_exclusions_and_existing_link_are_not_duplicated():
    source = '<html><body><a href="/dashboard">Dashboard</a></body></html>'
    assert inject_dashboard_link(source, "/sales") == source
    plain = "<html><body>Login</body></html>"
    assert inject_dashboard_link(plain, "/login") == plain
    assert inject_dashboard_link(plain, "/dashboard") == plain
    assert inject_dashboard_link(plain, "/change-password") == plain


def test_main_installs_global_navigation_after_routes():
    main = (ROOT / "src/main.py").read_text(encoding="utf-8")
    assert "TLC_GLOBAL_DASHBOARD_RETURN_LINK_R1" in main
    assert "install_global_dashboard_navigation(app)" in main


def test_middleware_decorates_html_but_not_json_or_dashboard():
    app = FastAPI()

    @app.get("/page", response_class=HTMLResponse)
    def page():
        return "<html><body>Page</body></html>"

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard():
        return "<html><body>Dashboard</body></html>"

    install_global_dashboard_navigation(app)
    client = TestClient(app)
    page_response = client.get("/page")
    assert page_response.status_code == 200
    assert MARKER in page_response.text
    assert MARKER not in client.get("/dashboard").text
    assert client.get("/openapi.json").headers["content-type"].startswith("application/json")
