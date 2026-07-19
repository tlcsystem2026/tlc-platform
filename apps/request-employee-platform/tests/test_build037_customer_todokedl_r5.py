from pathlib import Path


def test_r3_regression_test_matches_final_legacy_response_contract():
    test_file = Path(__file__).with_name(
        "test_build037_customer_todokedl_r3.py"
    )
    text = test_file.read_text(encoding="utf-8")
    assert 'created.json() == {"imported": 1, "created": 1, "updated": 0}' in text
    assert 'updated.json() == {"imported": 1, "created": 0, "updated": 1}' in text
    assert 'created.json()["inserted"]' not in text
