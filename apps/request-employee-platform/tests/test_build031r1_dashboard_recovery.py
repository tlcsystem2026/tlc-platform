from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_runtime_build031r1():
    r = client.get("/api/system/runtime")
    assert r.status_code == 200
    assert r.json()["version"] == "0.31.1-dashboard-recovery"

def test_root_redirects_to_dashboard():
    r = client.get("/", follow_redirects=False)
    assert r.status_code in {307, 308}
    assert r.headers["location"] == "/dashboard"

def test_dashboard_page_contract_contains_restored_sections():
    r = client.get("/dashboard")
    assert r.status_code == 200
    html = r.text
    required = [
        "数字员工中心",
        "AI业务支持系统",
        "受控部署（TEST）",
        "部署下载包",
        "今日业务TODO",
        "重要异常与领导关注",
        "业务入口",
    ]
    for text in required:
        assert text in html
    for text in ["核心业务快捷入口", "static-business-entrances"]:
        assert text not in html

def test_dashboard_summary_contract():
    r = client.get("/api/dashboard/summary")
    assert r.status_code == 200
    data = r.json()
    assert len(data["navigator"]) >= 6
    assert len(data["performance"]) >= 6
    assert any(x["title"] == "AI数字员工" for x in data["navigator"])
    removed = {
        "请求书处理", "请求书审核台", "客户跟踪与分析", "银行维护与流水格式",
        "销售数据一览", "应收管理", "银行到账核对", "领导审核",
    }
    assert not removed.intersection(x["title"] for x in data["navigator"])
