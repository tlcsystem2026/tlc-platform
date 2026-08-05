from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_authentication_service import audit_rows, bootstrap, change_password, current_session, iso, login, logout, now


INITIAL = "InitialPass123"
CHANGED = "ChangedPass456"


def database(tmp_path):
    return sessionmaker(bind=create_engine(f"sqlite:///{tmp_path / 'auth.sqlite3'}"))()


def test_bootstrap_login_first_change_logout_and_audit(tmp_path):
    db = database(tmp_path)
    boot = bootstrap(db, "E001", "admin", "系统管理员", INITIAL, "127.0.0.1")
    assert boot["must_change_password"] is True
    with pytest.raises(ValueError, match="已经设置"):
        bootstrap(db, "E002", "other", "其他", INITIAL, "127.0.0.1")
    first = login(db, "admin", INITIAL, "127.0.0.1", "pytest")
    assert first["must_change_password"] is True
    second = login(db, "admin", INITIAL, "127.0.0.1", "pytest-second")
    assert current_session(db, second["token"])
    changed = change_password(db, first["token"], INITIAL, CHANGED, "127.0.0.1")
    assert changed["other_sessions_revoked"] is True
    assert current_session(db, second["token"]) is None
    assert current_session(db, first["token"])["must_change_password"] == 0
    logout(db, first["token"], "127.0.0.1")
    assert current_session(db, first["token"]) is None
    assert {x["event_type"] for x in audit_rows(db)} >= {"BOOTSTRAP_SUPER_ADMIN", "LOGIN_SUCCESS", "PASSWORD_CHANGED", "LOGOUT"}


def test_bad_password_lock_disabled_account_and_timeout(tmp_path):
    db = database(tmp_path);boot = bootstrap(db, "E001", "admin", "系统管理员", INITIAL, "127.0.0.1")
    for _ in range(5):
        with pytest.raises(PermissionError):login(db, "admin", "WrongPassword123", "10.0.0.8", "pytest")
    with pytest.raises(PermissionError, match="锁定"):
        login(db, "admin", INITIAL, "10.0.0.8", "pytest")
    db.execute(text("UPDATE tlc_auth_credential SET failed_attempts=0,locked_until='' WHERE user_id=:user"), {"user": boot["user_id"]});db.commit()
    result = login(db, "admin", INITIAL, "10.0.0.8", "pytest")
    db.execute(text("UPDATE tlc_auth_session SET last_seen_at=:old WHERE id=:id"), {"old": iso(now()-timedelta(hours=1)), "id": result["session_id"]});db.commit()
    assert current_session(db, result["token"]) is None
    db.execute(text("UPDATE tlc_user_master SET active=0 WHERE id=:user"), {"user": boot["user_id"]});db.commit()
    with pytest.raises(PermissionError, match="停用"):
        login(db, "admin", INITIAL, "10.0.0.8", "pytest")


def test_authentication_source_contracts():
    app = Path(__file__).parents[1]
    service = (app / "src/services/tlc_authentication_service.py").read_text(encoding="utf-8")
    route = (app / "src/api/routes/tlc_authentication.py").read_text(encoding="utf-8")
    main = (app / "src/main.py").read_text(encoding="utf-8")
    for value in ("pbkdf2_hmac", "httponly=True", "samesite=\"strict\"", "MAX_FAILURES", "IDLE_MINUTES", "tlc_auth_audit"):
        assert value in service + route
    assert "install_authentication(app)" in main
    for page in ("login.html", "change_password.html", "my_profile.html"):
        assert (app / "src/web/static" / page).exists()
