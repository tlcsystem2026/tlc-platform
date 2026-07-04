import argparse
from logging_config import configure_logging
from batch import process_directory

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pdf-dir", required=True)
    p.add_argument("--excel-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--money-tolerance", default="0")
    a = p.parse_args()
    configure_logging()
    results = process_directory(a.pdf_dir, a.excel_dir, a.output_dir, money_tolerance=a.money_tolerance)
    print(f"Processed: {len(results)}")
    print(f"OK: {sum(1 for r in results if r.get('status') == 'OK')}")
    print(f"Missing/Error: {sum(1 for r in results if r.get('status') != 'OK')}")

if __name__ == "__main__":
    main()
