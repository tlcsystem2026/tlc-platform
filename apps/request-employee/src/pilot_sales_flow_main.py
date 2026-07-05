import argparse
import json
from logging_config import configure_logging
from pilot_sales_flow import process_sales_flow

def main():
    p = argparse.ArgumentParser(description="Request Employee Sales Ledger Flow")
    p.add_argument("--pdf-dir", required=True)
    p.add_argument("--excel-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--sales-ledger", required=True)
    p.add_argument("--error-dir", required=True)
    p.add_argument("--money-tolerance", default="0")
    args = p.parse_args()

    configure_logging()
    rows = process_sales_flow(
        pdf_dir=args.pdf_dir,
        excel_dir=args.excel_dir,
        output_dir=args.output_dir,
        sales_ledger_path=args.sales_ledger,
        error_dir=args.error_dir,
        money_tolerance=args.money_tolerance,
    )
    print(json.dumps(rows, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
