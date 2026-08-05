import os
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_access_control_service import ensure_schema as ensure_access_schema
from src.services.tlc_authentication_service import PASSWORD_ITERATIONS, _hash_password, ensure_schema as ensure_auth_schema
from src.services.tlc_mfa_security_service import (
    check_login_mfa,
    create_step_up,
    enable_mfa,
    ensure_schema,
    list_sessions,
    rate_limit,
    record_login_anomaly,
    revoke_session,
    setup_mfa,
    totp,
    valid_step_up,
)


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'security.sqlite3'}")
    session = sessionmaker(bind=engine)()
    ensure_access_schema(session)
    ensure_auth_schema(session)
    ensure_schema(session)
    yield session
    session.close()
    engine.dispose()


def seed_user(db, user="u1", login="admin", password="StrongPassword1"):
    stamp = "2026-08-05T00:00:00+00:00"
    db.execute(text("INSERT INTO tlc_user_master(id,employee_no,name_en,name_ja,name_zh,email,mobile,login_id,legal_entity_id,department_id,active,valid_from,valid_to,created_at,updated_at) VALUES(:id,'E001','','','管理员','','',:login,'','',1,'','',:s,:s)"), {"id": user, "login": login, "s": stamp})
    salt = bytes(range(32))
    db.execute(text("INSERT INTO tlc_auth_credential VALUES(:u,:h,:salt,:i,0,0,'',:s,:s,:s)"), {"u": user, "h": _hash_password(password, salt), "salt": salt.hex(), "i": PASSWORD_ITERATIONS, "s": stamp})
    db.commit()


def test_totp_enable_login_and_replay_protection(db):
    seed_user(db)
    setup = setup_mfa(db, "u1", "admin")
    code = totp(setup["secret"], int(time.time() // 30))
    assert enable_mfa(db, "u1", code)["enabled"] is True
    with pytest.raises(ValueError):
        setup_mfa(db, "u1", "admin")
    with pytest.raises(PermissionError, match="required"):
        check_login_mfa(db, "u1", "")
    with pytest.raises(PermissionError, match="invalid"):
        check_login_mfa(db, "u1", "000000")
    with pytest.raises(PermissionError, match="invalid"):
        check_login_mfa(db, "u1", code)


def test_step_up_password_and_expiring_token(db):
    seed_user(db)
    result = create_step_up(db, "u1", "StrongPassword1", "", "127.0.0.1")
    assert result["expires_in"] == 300
    assert valid_step_up(db, "u1", result["token"])
    assert not valid_step_up(db, "u2", result["token"])
    with pytest.raises(PermissionError):
        create_step_up(db, "u1", "wrong", "", "127.0.0.1")


def test_sessions_can_be_viewed_and_forcibly_revoked(db):
    seed_user(db)
    stamp = "2026-08-05T00:00:00+00:00"
    db.execute(text("INSERT INTO tlc_auth_session VALUES('s1','hash','u1','127.0.0.1','browser',:s,:s,'2099-01-01T00:00:00+00:00','','')"), {"s": stamp})
    db.commit()
    assert len(list_sessions(db, "u1")) == 1
    assert revoke_session(db, "s1", "u1")["revoked"]
    assert db.execute(text("SELECT revoke_reason FROM tlc_auth_session WHERE id='s1'")).scalar_one() == "FORCED_LOGOUT"


def test_rate_limit_and_new_ip_anomaly(db):
    for _ in range(3):
        assert rate_limit(db, "login:127.0.0.1", 3, 60)
    assert not rate_limit(db, "login:127.0.0.1", 3, 60)
    assert record_login_anomaly(db, "u1", "10.0.0.1")["new_ip"] is False
    assert record_login_anomaly(db, "u1", "10.0.0.2")["new_ip"] is True
    assert record_login_anomaly(db, "u1", "10.0.0.2")["new_ip"] is False


def test_source_contracts_are_integrated():
    root = Path(__file__).parents[1]
    auth = (root / "src/api/routes/tlc_authentication.py").read_text(encoding="utf-8")
    service = (root / "src/services/tlc_authentication_service.py").read_text(encoding="utf-8")
    permission = (root / "src/services/tlc_api_permission_service.py").read_text(encoding="utf-8")
    main = (root / "src/main.py").read_text(encoding="utf-8")
    for contract in ("mfa_code", "rate_limit", "valid_step_up", "step_up_required", "TLC_MFA_SECURITY_AUDIT_R1"):
        assert contract in auth
    assert "check_login_mfa" in service
    assert "record_login_anomaly" in service
    assert "PASSWORD_CHANGED" in service and "id<>:current" in service
    assert '"/security-center": "SECURITY_AUDIT"' in permission
    assert "tlc_mfa_security_router" in main
