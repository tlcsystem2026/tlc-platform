from __future__ import annotations
from pathlib import Path
import logging

from pairing.file_pairer import FilePairer
from parser.tokyo_koibito_pdf_parser import TokyoKoibitoPDFParser
from parser.tokyo_koibito_excel_parser import TokyoKoibitoExcelParser
from compare.compare_engine import CompareEngine
from compare.difference_classifier import classify_differences
from diagnostics.parser_diagnostics import document_diagnostics
from validation.reconciliation import reconcile
from validation.acceptance_score import acceptance_score
from report.difference_report import write_difference_report
from report.html_report import write_html_report
from tlc_io.json_store import save_json
from output.sales_ledger import SalesLedger
from output.error_router import route_error_pair

log = logging.getLogger(__name__)

def process_sales_flow(pdf_dir, excel_dir, output_dir, sales_ledger_path, error_dir, money_tolerance="0"):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    error_dir = Path(error_dir)
    ledger = SalesLedger(sales_ledger_path)
    results = []

    for pair in FilePairer().pair(pdf_dir, excel_dir):
        if pair["status"] != "PAIRED":
            results.append({**pair, "action": "NO_REGISTER"})
            continue

        pdf = Path(pair["pdf"])
        excel = Path(pair["excel"])

        try:
            pdf_doc = TokyoKoibitoPDFParser().parse(pdf)
            excel_doc = TokyoKoibitoExcelParser().parse(excel)
            pd = document_diagnostics(pdf_doc)
            ed = document_diagnostics(excel_doc)
            diffs = CompareEngine(money_tolerance).compare(pdf_doc, excel_doc)
            diffs = classify_differences(diffs, pd, ed)
            recon = {"pdf": reconcile(pdf_doc, money_tolerance), "excel": reconcile(excel_doc, money_tolerance)}
            score = acceptance_score(pdf_doc, excel_doc, diffs)

            request_no = pdf_doc.request_no or excel_doc.request_no or pdf.stem
            job = out / request_no
            job.mkdir(parents=True, exist_ok=True)

            save_json(pdf_doc.to_dict(), job / "pdf.json")
            save_json(excel_doc.to_dict(), job / "excel.json")
            save_json(diffs, job / "differences.json")
            save_json(recon, job / "reconciliation.json")
            save_json(score, job / "acceptance_score.json")
            write_difference_report(diffs, job / "differences.xlsx")
            write_html_report(diffs, job / "differences.html", title=f"Difference Report {request_no}")

            has_errors = bool(diffs) or bool(recon["pdf"]) or bool(recon["excel"]) or score["grade"] != "PILOT_READY"

            if has_errors:
                reason = {
                    "request_no": request_no,
                    "action": "ROUTE_TO_ERROR",
                    "difference_count": len(diffs),
                    "pdf_reconciliation_issues": recon["pdf"],
                    "excel_reconciliation_issues": recon["excel"],
                    "acceptance_score": score,
                    "pdf": str(pdf),
                    "excel": str(excel),
                }
                error_target = route_error_pair(pdf, excel, error_dir, reason)
                results.append({**pair, "request_no": request_no, "action": "ROUTE_TO_ERROR",
                                "error_folder": str(error_target), "differences": len(diffs),
                                "acceptance": score["grade"], "status": "REVIEW_REQUIRED"})
            else:
                rows = ledger.append_request(pdf_doc, str(pdf), str(excel))
                results.append({**pair, "request_no": request_no, "action": "REGISTER_SALES_LEDGER",
                                "sales_ledger": str(Path(sales_ledger_path)), "rows_added": rows,
                                "status": "REGISTERED"})
        except Exception as exc:
            log.exception("Sales flow failed for %s", pdf.name)
            reason = {"request_no": pdf.stem, "action": "ROUTE_TO_ERROR", "error": str(exc),
                      "error_type": type(exc).__name__, "pdf": str(pdf), "excel": str(excel)}
            error_target = route_error_pair(pdf, excel, error_dir, reason)
            results.append({**pair, "action": "ROUTE_TO_ERROR", "error_folder": str(error_target),
                            "status": "ERROR", "error": str(exc)})

    save_json(results, out / "sales_flow_summary.json")
    return results
