from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_build032r4_v21_preserves_dashboard_contract():
    r = client.get("/dashboard")
    assert r.status_code == 200
    for text in ["数字员工中心","AI业务支持系统","受控部署（TEST）","部署下载包","今日业务TODO","重要异常与领导关注","业务入口","核心业务快捷入口","请求书审核台","销售数据一览","银行到账核对","AI数字员工"]:
        assert text in r.text

def test_build032r4_v21_route_registered():
    r = client.get("/api/customer-reconciliation/page")
    assert r.status_code == 200
    assert "客户对账清款基准设置" in r.text
