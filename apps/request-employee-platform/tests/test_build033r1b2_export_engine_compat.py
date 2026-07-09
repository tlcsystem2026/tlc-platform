from src.services.export_engine import selfcheck_export_content, selfcheck_export_response


def test_build033r1b2_legacy_selfcheck_alias_exists():
    assert selfcheck_export_content is not None
    assert selfcheck_export_response is not None
