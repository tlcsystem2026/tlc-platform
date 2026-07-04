import argparse
from logging_config import configure_logging
from batch_stable import process_directory_stable

def main():
    p = argparse.ArgumentParser(description="Stable Request Employee batch runner")
    p.add_argument("--pdf-dir", required=True)
    p.add_argument("--excel-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--money-tolerance", default="0")
    p.add_argument("--force", action="store_true")
    a = p.parse_args()
    configure_logging()
    rows = process_directory_stable(
        a.pdf_dir, a.excel_dir, a.output_dir,
        money_tolerance=a.money_tolerance, force=a.force
    )
    print(f"Total: {len(rows)}")
    for status in ("OK", "SKIPPED_DUPLICATE", "ERROR", "MISSING_EXCEL", "MISSING_PDF"):
        print(f"{status}: {sum(1 for r in rows if r.get('status') == status)}")

if __name__ == "__main__":
    main()
