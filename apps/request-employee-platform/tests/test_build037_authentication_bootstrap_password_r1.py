from pathlib import Path
import pytest

from src.services.tlc_authentication_service import _password_policy


def test_ascii_password_rule():
    _password_policy("StrongPassword1")


def test_full_width_equivalent_is_accepted():
    _password_policy("ＳｔｒｏｎｇＰａｓｓｗｏｒｄ１")


@pytest.mark.parametrize("password,missing", [
    ("Short1A", "长度不足12位"),
    ("lowercaseonly1", "大写英文字母"),
    ("UPPERCASEONLY1", "小写英文字母"),
    ("NoDigitsPassword", "数字"),
])
def test_error_identifies_exact_missing_rule(password, missing):
    with pytest.raises(ValueError, match=missing):
        _password_policy(password)


def test_page_has_separate_bootstrap_login_and_live_rules():
    page = (Path(__file__).parents[1] / "src/web/static/login.html").read_text(encoding="utf-8")
    for contract in ("bootstrapLoginId", "bootstrapPasswordConfirm", "两次输入的密码完全一致", "checkPassword", "normalize('NFKC')", "当前${[...p].length}位"):
        assert contract in page
