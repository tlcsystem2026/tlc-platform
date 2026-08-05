from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_access_control_service import assign_roles, overview as access_overview, save_user
from src.services.tlc_super_admin_service import grant, internal_ip_allowed, overview, revoke


def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'super-admin.sqlite3'}")
    return sessionmaker(bind=engine)()


def test_super_admin_is_separate_and_last_admin_is_protected(tmp_path):
    db = database(tmp_path)
    user1 = save_user(db, {"employee_no": "E001", "login_id": "e001", "name_zh": "甲", "actor": "test"})
    user2 = save_user(db, {"employee_no": "E002", "login_id": "e002", "name_zh": "乙", "actor": "test"})
    assert grant(db, user1["id"], "", "首次设置", "GRANT_SUPER_ADMIN")["bootstrap"] is True
    assert grant(db, user2["id"], user1["id"], "双人管理", "GRANT_SUPER_ADMIN")["granted"] is True
    assert revoke(db, user2["id"], user1["id"], "人员调整", "REVOKE_SUPER_ADMIN")["revoked"] is True
    with pytest.raises(ValueError, match="至少必须保留"):
        revoke(db, user1["id"], user1["id"], "错误操作", "REVOKE_SUPER_ADMIN")
    with pytest.raises(ValueError, match="超级管理员设置页面"):
        assign_roles(db, user1["id"], ["SUPER_ADMIN"], "ordinary")
    assert db.execute(text("SELECT COUNT(*) FROM tlc_user_role WHERE user_id=:u AND role_code='SUPER_ADMIN'"), {"u": user1["id"]}).scalar_one() == 1
    permissions = db.execute(text("SELECT COUNT(*) FROM tlc_role_permission WHERE role_code='SUPER_ADMIN' AND allowed=1 AND data_scope='ALL'")).scalar_one()
    assert permissions == len(access_overview(db)["modules"]) * len(access_overview(db)["actions"])
    assert overview(db)["active_count"] == 1


def test_internal_ip_and_source_contracts():
    assert internal_ip_allowed("127.0.0.1")
    assert internal_ip_allowed("::1")
    assert not internal_ip_allowed("192.168.1.10")
    app = Path(__file__).parents[1]
    page = (app / "src/web/static/access_control_center.html").read_text(encoding="utf-8")
    route = (app / "src/api/routes/tlc_access_control.py").read_text(encoding="utf-8")
    super_route = (app / "src/api/routes/tlc_super_admin.py").read_text(encoding="utf-8")
    assert "SUPER_ADMIN" not in route.split('result["roles"]=', 1)[0][-1:]
    assert 'x["role_code"]!="SUPER_ADMIN"' in route
    assert "require_internal(request)" in super_route
    assert "GRANT_SUPER_ADMIN" in (app / "src/web/static/super_admin_management.html").read_text(encoding="utf-8")
    assert "role-check" in page
