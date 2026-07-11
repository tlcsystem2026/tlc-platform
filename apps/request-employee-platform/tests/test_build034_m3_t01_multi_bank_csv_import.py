from fastapi.testclient import TestClient
from src.main import app
from src.services.multi_bank_csv_import_service import detect_bank_csv, parse_bank_csv

client=TestClient(app)

SUGAMO = """契約店舗コード,店舗名,科目,口座番号,照会期間,照会対象
003,板橋支店,普通,3172482,指定なし,すべて


日付,摘要,お支払い金額,お預かり金額,残高
2026/05/14,振込入金＊,アマゾンジヤパン（ト,49216,1401512
2026/05/15,手数料,1100,ＦＢ基本料,1400412
""".encode("cp932")

YUCH0 = """お客さま口座情報
現在高：,"48,465,178",円,
お客さま口座番号：10190-94472061
取引日,入出金明細ＩＤ,受入金額（円）,払出金額（円）,詳細１,詳細２,現在（貸付）高,
20260702,202607020000001,66000,,送金,高山　全威,35954573,
20260702,202607020000004,,165,料　金,,26103133,
""".encode("cp932")

def test_detect_and_parse_sugamo_by_amount_columns():
    assert detect_bank_csv(SUGAMO)=="SUGAMO_SHINKIN"
    rows=parse_bank_csv(SUGAMO,source_file="sugamo.csv",import_batch_id="B1")
    assert len(rows)==2
    assert rows[0].direction=="CREDIT"
    assert rows[0].deposit_amount=="49216"
    assert rows[0].counterparty=="アマゾンジヤパン（ト"
    assert rows[1].direction=="DEBIT"
    assert rows[1].withdrawal_amount=="1100"
    assert rows[1].counterparty=="ＦＢ基本料"

def test_detect_and_parse_japan_post():
    assert detect_bank_csv(YUCH0)=="JAPAN_POST_BANK"
    rows=parse_bank_csv(YUCH0,source_file="yucho.csv",import_batch_id="B2")
    assert len(rows)==2
    assert rows[0].transaction_id=="202607020000001"
    assert rows[0].direction=="CREDIT"
    assert rows[1].direction=="DEBIT"
    assert rows[1].withdrawal_amount=="165"

def test_import_endpoint_is_idempotent():
    first=client.post("/api/bank-import/csv?source_name=yucho.csv",content=YUCH0,headers={"content-type":"text/csv"})
    assert first.status_code==200
    assert first.json()["parsed"]==2
    second=client.post("/api/bank-import/csv?source_name=yucho.csv",content=YUCH0,headers={"content-type":"text/csv"})
    assert second.status_code==200
    assert second.json()["existing"]>=2
