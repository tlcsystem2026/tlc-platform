from __future__ import annotations
import argparse,json
from pathlib import Path
from parser.tokyo_koibito_pdf_parser import TokyoKoibitoPDFParser
from parser.tokyo_koibito_excel_parser import TokyoKoibitoExcelParser
from compare.compare_engine import CompareEngine
from compare.difference_classifier import classify_differences
from diagnostics.parser_diagnostics import document_diagnostics,write_diagnostics
from diagnostics.raw_export import export_pdf_raw,export_excel_cells
from validation.acceptance_score import acceptance_score
from validation.reconciliation import reconcile
from report.difference_report import write_difference_report
from report.html_report import write_html_report
from tlc_io.json_store import save_json

def main():
    p=argparse.ArgumentParser();p.add_argument("--pdf",required=True);p.add_argument("--excel",required=True)
    p.add_argument("--output-dir",required=True);p.add_argument("--money-tolerance",default="0");a=p.parse_args()
    pdf=TokyoKoibitoPDFParser().parse(a.pdf); exc=TokyoKoibitoExcelParser().parse(a.excel)
    pd,ed=document_diagnostics(pdf),document_diagnostics(exc)
    diffs=CompareEngine(a.money_tolerance).compare(pdf,exc)
    diffs=classify_differences(diffs,pd,ed)
    out=Path(a.output_dir)/(pdf.request_no or exc.request_no or Path(a.pdf).stem);out.mkdir(parents=True,exist_ok=True)
    save_json(pdf.to_dict(),out/"pdf.json");save_json(exc.to_dict(),out/"excel.json")
    save_json(diffs,out/"differences.json");write_diagnostics(pdf,out/"pdf_diagnostics.json");write_diagnostics(exc,out/"excel_diagnostics.json")
    export_pdf_raw(a.pdf,out/"pdf_raw.txt");export_excel_cells(a.excel,out/"excel_cells.csv")
    recon={"pdf":reconcile(pdf,a.money_tolerance),"excel":reconcile(exc,a.money_tolerance)}
    save_json(recon,out/"reconciliation.json")
    score=acceptance_score(pdf,exc,diffs);save_json(score,out/"acceptance_score.json")
    write_difference_report(diffs,out/"differences.xlsx");write_html_report(diffs,out/"differences.html")
    print(json.dumps({"request_no":pdf.request_no,"differences":len(diffs),"reconciliation":recon,"acceptance":score,"output":str(out)},ensure_ascii=False,indent=2))
if __name__=="__main__":main()

