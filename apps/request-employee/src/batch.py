from pathlib import Path
import json
import logging
from parser.pdf_parser import PDFParser
from parser.excel_parser import ExcelParser
from compare.compare_engine import CompareEngine
from report.difference_report import write_difference_report
from report.html_report import write_html_report
from report.diagnostics_report import write_diagnostics_workbook
from diagnostics.parser_diagnostics import document_diagnostics
from io.json_store import save_json
from pairing.file_pairer import FilePairer

log = logging.getLogger(__name__)

def process_directory(pdf_dir, excel_dir, output_dir, money_tolerance="0"):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    diagnostics_rows = []

    for pair in FilePairer().pair(pdf_dir, excel_dir):
        if pair["status"] != "PAIRED":
            results.append(pair)
            continue

        pdf = Path(pair["pdf"])
        excel = Path(pair["excel"])
        try:
            pdf_doc = PDFParser().parse(pdf)
            excel_doc = ExcelParser().parse(excel)
            diagnostics_rows.append({"kind": "PDF", **document_diagnostics(pdf_doc)})
            diagnostics_rows.append({"kind": "EXCEL", **document_diagnostics(excel_doc)})

            diffs = CompareEngine(money_tolerance=money_tolerance).compare(pdf_doc, excel_doc)

            job_name = pdf_doc.request_no or excel_doc.request_no or pdf.stem
            job = out / job_name
            job.mkdir(exist_ok=True)

            save_json(pdf_doc.to_dict(), job / "pdf.json")
            save_json(excel_doc.to_dict(), job / "excel.json")
            save_json(diffs, job / "differences.json")
            save_json(document_diagnostics(pdf_doc), job / "pdf_diagnostics.json")
            save_json(document_diagnostics(excel_doc), job / "excel_diagnostics.json")
            write_difference_report(diffs, job / "differences.xlsx")
            write_html_report(diffs, job / "differences.html", title=f"Difference Report {job_name}")

            results.append({
                **pair,
                "job": str(job),
                "request_no": job_name,
                "differences": len(diffs),
                "errors": sum(1 for d in diffs if d.get("severity") == "ERROR"),
                "warnings": sum(1 for d in diffs if d.get("severity") == "WARNING"),
                "status": "OK",
            })
        except Exception as exc:
            log.exception("Failed pair %s", pdf.stem)
            results.append({**pair, "status": "ERROR", "error": str(exc)})

    save_json(results, out / "batch_summary.json")
    save_json(diagnostics_rows, out / "parser_diagnostics.json")
    write_diagnostics_workbook(diagnostics_rows, out / "parser_diagnostics.xlsx")
    return results
