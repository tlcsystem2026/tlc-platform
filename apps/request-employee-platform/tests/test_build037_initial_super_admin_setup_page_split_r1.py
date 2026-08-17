from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.services.tlc_authentication_service import bootstrap, bootstrap_available

ROOT = Path(__file__).parents[1]


def test_bootstrap_availability_closes_after_first_setup(tmp_path):
    db = sessionmaker(bind=create_engine(f"sqlite:///{tmp_path / 'split.sqlite3'}"))()
    assert bootstrap_available(db) is True
    bootstrap(db, "E001", "admin", "系统管理员", "InitialPass123", "127.0.0.1")
    assert bootstrap_available(db) is False


def test_login_contains_only_login_controls():
    page = (ROOT / "src/web/static/login.html").read_text(encoding="utf-8")
    assert "TLC_INITIAL_SUPER_ADMIN_SETUP_PAGE_SPLIT_R1" in page
    assert 'id="loginId"' in page and 'id="password"' in page and 'id="mfaCode"' in page
    for forbidden in ("employeeNo", "bootstrapLoginId", "bootstrapPassword", "doBootstrap"):
        assert forbidden not in page


def test_initial_setup_page_and_route_are_separate_and_guarded():
    page = (ROOT / "src/web/static/initial_super_admin_setup.html").read_text(encoding="utf-8")
    route = (ROOT / "src/api/routes/tlc_authentication.py").read_text(encoding="utf-8")
    for value in ("employeeNo", "bootstrapLoginId", "nameZh", "bootstrapPassword", "bootstrapPasswordConfirm", "doBootstrap"):
        assert value in page
    assert '/initial-super-admin-setup' in route
    assert "internal_ip_allowed(_ip(request))" in route
    assert "bootstrap_available(db)" in route
    assert 'RedirectResponse("/login", status_code=303)' in route
    assert '"/initial-super-admin-setup"' in route.split("PUBLIC_PATHS", 1)[1].split("}", 1)[0]


def test_existing_bootstrap_api_security_remains():
    route = (ROOT / "src/api/routes/tlc_authentication.py").read_text(encoding="utf-8")
    block = route.split('@router.post("/api/auth/bootstrap")', 1)[1].split('@router.post("/api/auth/login")', 1)[0]
    assert "internal_ip_allowed(_ip(request))" in block
    assert "bootstrap(" in block
