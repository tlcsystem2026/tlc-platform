from pathlib import Path

import pytest

from src.services.tlc_customer_name_identity_service import resolve_language_code

ROOT=Path(__file__).parents[1]


def test_language_auto_detection_is_conservative():
    assert resolve_language_code("株式会社テスト","auto") == "ja"
    assert resolve_language_code("株式会社三友貿易","auto") == "und"
    assert resolve_language_code("三友贸易","auto") == "und"
    assert resolve_language_code("三友贸易","zh") == "zh"
    assert resolve_language_code("三友貿易","ja") == "ja"
    with pytest.raises(ValueError):
        resolve_language_code("Test","en")


def test_page_reads_name_input_explicitly_and_exposes_language_choices():
    page=(ROOT/"src/web/static/customer_name_identity_center.html").read_text(encoding="utf-8")
    assert "TLC_CUSTOMER_NAME_IDENTITY_LANGUAGE_REGISTRATION_R1" in page
    assert "document.getElementById('name')" in page
    assert "name_value:value" in page
    for value in ("auto","zh","ja","und"):
        assert f"['{value}'" in page
