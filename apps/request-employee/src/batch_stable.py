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
from io.json_store import save_json
from io.job_fingerprint import pair_fingerprint
from io.job_registry import JobRegistry

log = logging.getLogger(__name__)

def process_directory_stable(pdf_dir, excel_dir, output_dir, money_tolerance="0", force=False):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    failed = out / "_failed"
    failed.mkdir(exist_ok=True)
    registry = JobRegistry(out / "job_registry.json")
    results = []

    for pair in FilePairer().pair(pdf_dir, excel_dir):
        if pair["status"] != "PAIRED":
            results.append(pair)
            continue

        pdf, excel = Path(pair["pdf"]), Path(pair["excel"])
        fingerprint = pair_fingerprint(pdf, excel)

        if not force and registry.contains_success(fingerprint):
            results.append({**pair, "fingerprint": fingerprint, "status": "SKIPPED_DUPLICATE"})
            continue

        try:
            pdf_doc = TokyoKoibitoPDFParser().parse(pdf)
            excel_doc = TokyoKoibitoExcelParser().parse(excel)
            pd = document_diagnostics(pdf_doc)
            ed = document_diagnostics(excel_doc)

            diffs = CompareEngine(money_tolerance).compare(pdf_doc, excel_doc)
            diffs = classify_differences(diffs, pd, ed)
            recon = {
                "pdf": reconcile(pdf_doc, money_tolerance),
                "excel": reconcile(excel_doc, money_tolerance),
            }
            score = acceptance_score(pdf_doc, excel_doc, diffs)

            job_name = pdf_doc.request_no or excel_doc.request_no or pdf.stem
            job = out / job_name
            job.mkdir(exist_ok=True)

            save_json(pdf_doc.to_dict(), job / "pdf.json")
            save_json(excel_doc.to_dict(), job / "excel.json")
            save_json(diffs, job / "differences.json")
            save_json(recon, job / "reconciliation.json")
            save_json(score, job / "acceptance_score.json")
            write_difference_report(diffs, job / "differences.xlsx")
            write_html_report(diffs, job / "differences.html", title=f"Difference Report {job_name}")

            registry.record(fingerprint, "SUCCESS", request_no=job_name, pdf=str(pdf), excel=str(excel))
            results.append({
                **pair, "fingerprint": fingerprint, "request_no": job_name,
                "differences": len(diffs), "acceptance": score["grade"], "status": "OK",
            })
        except Exception as exc:
            log.exception("Isolated failure for pair %s / %s", pdf.name, excel.name)
            error_file = failed / f"{pdf.stem}.error.json"
            save_json({
                "pdf": str(pdf), "excel": str(excel),
                "fingerprint": fingerprint, "error_type": type(exc).__name__,
                "error": str(exc),
            }, error_file)
            registry.record(fingerprint, "FAILED", pdf=str(pdf), excel=str(excel), error=str(exc))
            results.append({**pair, "fingerprint": fingerprint, "status": "ERROR", "error": str(exc)})

    save_json(results, out / "batch_stable_summary.json")
    return results
