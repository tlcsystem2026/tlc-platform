from tlc_io.job_registry import JobRegistry

def test_registry_success(tmp_path):
    r = JobRegistry(tmp_path / "registry.json")
    assert not r.contains_success("abc")
    r.record("abc", "SUCCESS", request_no="LY01006")
    assert r.contains_success("abc")

def test_registry_failed_is_retryable(tmp_path):
    r = JobRegistry(tmp_path / "registry.json")
    r.record("abc", "FAILED")
    assert not r.contains_success("abc")

