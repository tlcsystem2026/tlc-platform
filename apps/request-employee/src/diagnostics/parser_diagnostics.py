from __future__ import annotations
from pathlib import Path
import json

REQUIRED_FIELDS = ["request_no", "request_date", "customer_name", "total_amount"]

def document_diagnostics(doc) -> dict:
    data = doc.to_dict()
    missing = [field for field in REQUIRED_FIELDS if not data.get(field) or data.get(field) == "0"]
    line_count = len(data.get("lines", []))
    return {
        "source_file": data.get("source_file", ""),
        "request_no": data.get("request_no", ""),
        "request_date": data.get("request_date", ""),
        "customer_name": data.get("customer_name", ""),
        "total_amount": data.get("total_amount", ""),
        "line_count": line_count,
        "missing_fields": missing,
        "status": "OK" if not missing and line_count > 0 else "NEEDS_REVIEW",
    }

def write_diagnostics(doc, output_path: str | Path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(document_diagnostics(doc), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
