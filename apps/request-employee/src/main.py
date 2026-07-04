from __future__ import annotations
import argparse, json
from pathlib import Path

from parser.pdf_parser import PDFParser
from parser.excel_parser import ExcelParser
from compare.compare_engine import CompareEngine
from report.difference_report import write_difference_report

def main():
    ap = argparse.ArgumentParser(description="TLC Request Employee Business MVP")
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--excel", required=True)
    ap.add_argument("--output", default="difference.xlsx")
    args = ap.parse_args()

    pdf_doc = PDFParser().parse(args.pdf)
    excel_doc = ExcelParser().parse(args.excel)
    diffs = CompareEngine().compare(pdf_doc, excel_doc)
    write_difference_report(diffs, args.output)

    print(json.dumps({
        "pdf": pdf_doc.to_dict(),
        "excel": excel_doc.to_dict(),
        "difference_count": len(diffs),
        "report": str(Path(args.output).resolve()),
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
