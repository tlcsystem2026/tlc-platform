from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app


ROOT = Path(__file__).parents[1]
PAGE = (
    ROOT
    / "src"
    / "web"
    / "static"
    / "tlc_bank_account_master.html"
)

client = TestClient(app)


def test_bank_account_tab_switch_r2_contract():
    page = PAGE.read_text(encoding="utf-8")

    assert "TLC_BANK_ACCOUNT_TAB_SWITCH_R2" in page
    assert 'id="tabButtonBanks"' in page
    assert 'id="tabButtonAccounts"' in page
    assert 'document.getElementById("tabButtonBanks")' in page
    assert 'document.getElementById("tabButtonAccounts")' in page
    assert 'setBankMaintenanceTab("banks")' in page
    assert 'setBankMaintenanceTab("accounts")' in page
    assert "window.showTab = setBankMaintenanceTab" in page


def test_bank_account_tab_panels_still_exist():
    page = PAGE.read_text(encoding="utf-8")

    assert 'id="banks" class="tab active"' in page
    assert 'id="accounts" class="tab"' in page
    assert 'section.classList.toggle(' in page
    assert 'button.classList.toggle("active", selected)' in page


def test_bank_account_page_returns_r2_switcher():
    response = client.get("/tlc-bank-account-master")

    assert response.status_code == 200
    assert "TLC_BANK_ACCOUNT_TAB_SWITCH_R2" in response.text