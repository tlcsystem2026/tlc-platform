from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.formal_sales_ledger_service import (
    post_approved_pending_review,
)
from src.services.request_batch_compare_import_service import ensure_tables
from src.services.request_pending_review_service import (
    create_pending_review,
)
from src.services.request_tax_breakdown_service import (
    compare_tax_breakdowns,
    extract_tax_breakdown_from_excel,
    extract_tax_breakdown_from_text,
)


PDF_TEXT = """
10%対象額 ¥100,000
10%消費税 ¥10,000
10%税込金額 ¥110,000
軽減税率8%対象額 ¥50,000
軽減税率8%消費税 ¥4,000
軽減税率8%税込金額 ¥54,000
非課税 ¥3,000
免税 ¥2,000
御請求金額 ¥169,000
"""

EXCEL_DATA = {
    "sheets": [
        {
            "title": "請求書",
            "rows": [
                ["10%対象額", 100000],
                ["10%消費税", 10000],
                ["10%税込金額", 110000],
                ["軽減税率8%対象額", 50000],
                ["軽減税率8%消費税", 4000],
                ["軽減税率8%税込金額", 54000],
                ["非課税", 3000],
                ["免税", 2000],
                ["御請求金額", 169000],
            ],
        }
    ]
}


def make_db(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'tax.sqlite3').as_posix()}"
    )
    return engine, sessionmaker(bind=engine)()


def test_tax_breakdown_extracts_10_8_non_taxable_and_exempt():
    pdf = extract_tax_breakdown_from_text(PDF_TEXT)
    excel = extract_tax_breakdown_from_excel(EXCEL_DATA)

    assert pdf["taxable_amount_10"] == "100000"
    assert pdf["tax_amount_10"] == "10000"
    assert pdf["tax_inclusive_amount_10"] == "110000"
    assert pdf["taxable_amount_8"] == "50000"
    assert pdf["tax_amount_8"] == "4000"
    assert pdf["tax_inclusive_amount_8"] == "54000"
    assert pdf["non_taxable_amount"] == "3000"
    assert pdf["tax_exempt_amount"] == "2000"
    assert pdf["calculated_total_amount"] == "169000"

    assert excel == pdf
    assert compare_tax_breakdowns(pdf, excel) == ([], [])


def test_tax_breakdown_mismatch_has_rate_specific_code():
    pdf = extract_tax_breakdown_from_text(PDF_TEXT)
    excel = extract_tax_breakdown_from_excel(EXCEL_DATA)
    excel["tax_amount_8"] = "3999"

    codes, details = compare_tax_breakdowns(pdf, excel)
    assert "TAX_AMOUNT_8_MISMATCH" in codes
    assert any("tax_amount_8" in detail for detail in details)


def test_compare_item_has_tax_columns(tmp_path):
    engine, db = make_db(tmp_path)
    try:
        ensure_tables(db)
        columns = {
            row._mapping["name"]
            for row in db.execute(
                text("PRAGMA table_info(tlc_request_batch_compare_item)")
            ).all()
        }
        for required in [
            "pdf_tax_breakdown_json",
            "excel_tax_breakdown_json",
            "pdf_taxable_amount_10",
            "excel_taxable_amount_10",
            "pdf_tax_amount_8",
            "excel_tax_amount_8",
            "pdf_non_taxable_amount",
            "excel_tax_exempt_amount",
        ]:
            assert required in columns
    finally:
        db.close()
        engine.dispose()


def test_tax_breakdown_flows_to_business_review_and_sales_ledger(tmp_path):
    engine, db = make_db(tmp_path)
    try:
        payload = {
            "matched": True,
            "request_no": "TAX-REQ-001",
            "file_review_id": "FILE-REVIEW-001",
            "batch_id": "BATCH-001",
            "batch_item_id": "ITEM-001",
            "business_month": "202601",
            "request_document": {
                "request_date": "2026-01-10",
                "customer_id": "C001",
                "customer_name": "株式会社客户",
                "currency": "JPY",
                "taxable_amount_10": "100000",
                "tax_amount_10": "10000",
                "tax_inclusive_amount_10": "110000",
                "taxable_amount_8": "50000",
                "tax_amount_8": "4000",
                "tax_inclusive_amount_8": "54000",
                "non_taxable_amount": "3000",
                "tax_exempt_amount": "2000",
                "subtotal": "155000",
                "tax_amount": "14000",
                "total_amount": "169000",
            },
            "sources": {
                "pdf": "c:/completed/TAX-REQ-001.pdf",
                "excel": "c:/completed/TAX-REQ-001.xlsx",
            },
        }

        created = create_pending_review(db, payload)
        record = created["record"]
        assert record["taxable_amount_10"] == "100000"
        assert record["tax_amount_8"] == "4000"
        assert record["non_taxable_amount"] == "3000"

        db.execute(
            text(
                """
                UPDATE request_pending_review
                SET status='APPROVED',
                    reviewed_by='reviewer',
                    reviewed_at='now'
                WHERE id=:id
                """
            ),
            {"id": record["id"]},
        )
        db.commit()

        posted = post_approved_pending_review(db, record["id"])
        ledger = posted["ledger"]
        assert ledger["taxable_amount_10"] == "100000"
        assert ledger["tax_amount_10"] == "10000"
        assert ledger["taxable_amount_8"] == "50000"
        assert ledger["tax_amount_8"] == "4000"
        assert ledger["tax_exempt_amount"] == "2000"
        assert ledger["total_amount"] == "169000"
    finally:
        db.close()
        engine.dispose()


def test_business_review_page_displays_tax_breakdown():
    page = (
        Path(__file__).parents[1]
        / "src/web/static/request_review_workbench.html"
    ).read_text(encoding="utf-8")

    assert "BUILD037_REQUEST_TAX_BREAKDOWN_R1" in page
    for required in [
        "10%对象",
        "10%税",
        "8%对象",
        "8%税",
        "非课税",
        "免税",
        "taxable_amount_10",
        "tax_amount_8",
    ]:
        assert required in page
