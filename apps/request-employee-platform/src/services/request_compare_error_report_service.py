from __future__ import annotations

import csv
import html
import io
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

REPORT_FIELDS = [
    "request_no", "field", "excel_value", "pdf_value",
    "severity", "message", "excel_source", "pdf_source",
]


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Unsupported compare result type: {type(value)!r}")


def normalize_compare_result(compare_result: Any) -> dict[str, Any]:
    data = dict(_as_mapping(compare_result))
    sources = data.get("sources", {}) or {}
    differences = []
    for item in data.get("differences", []) or []:
        diff = dict(_as_mapping(item))
        differences.append({
            "request_no": str(data.get("request_no", "") or ""),
            "field": str(diff.get("field", "") or ""),
            "excel_value": str(diff.get("excel_value", diff.get("left", "")) or ""),
            "pdf_value": str(diff.get("pdf_value", diff.get("right", "")) or ""),
            "severity": str(diff.get("severity", "error") or "error"),
            "message": str(diff.get("message", "") or ""),
            "excel_source": str(data.get("excel_source", sources.get("excel", "")) or ""),
            "pdf_source": str(data.get("pdf_source", sources.get("pdf", "")) or ""),
        })
    return {
        "matched": bool(data.get("matched", not differences)),
        "request_no": str(data.get("request_no", "") or ""),
        "difference_count": len(differences),
        "differences": differences,
    }


def build_error_report_json(compare_result: Any) -> bytes | None:
    normalized = normalize_compare_result(compare_result)
    if normalized["matched"]:
        return None
    return json.dumps(normalized, ensure_ascii=False, indent=2).encode("utf-8")


def build_error_report_csv(compare_result: Any) -> bytes | None:
    normalized = normalize_compare_result(compare_result)
    if normalized["matched"]:
        return None
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=REPORT_FIELDS)
    writer.writeheader()
    writer.writerows(normalized["differences"])
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def build_error_report_html(compare_result: Any) -> str:
    normalized = normalize_compare_result(compare_result)
    request_no = html.escape(normalized["request_no"])
    if normalized["matched"]:
        return f"""<!doctype html><html><head><meta charset="utf-8"><title>Compare Result</title></head>
<body><h1>Request Compare Result</h1><p>Request No: {request_no}</p>
<p id="compare-status">MATCHED</p></body></html>"""

    rows = []
    for diff in normalized["differences"]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(diff['field'])}</td>"
            f"<td>{html.escape(diff['excel_value'])}</td>"
            f"<td>{html.escape(diff['pdf_value'])}</td>"
            f"<td>{html.escape(diff['severity'])}</td>"
            f"<td>{html.escape(diff['message'])}</td>"
            f"<td>{html.escape(diff['excel_source'])}</td>"
            f"<td>{html.escape(diff['pdf_source'])}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Compare Error Report</title>
<style>body{{font-family:Arial,sans-serif;margin:24px}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #bbb;padding:8px;text-align:left}}th{{background:#f2f2f2}}
.error{{color:#b00020;font-weight:bold}}</style></head>
<body><h1>Request Compare Error Report</h1><p>Request No: {request_no}</p>
<p id="compare-status" class="error">MISMATCH: {normalized['difference_count']}</p>
<table><thead><tr><th>Field</th><th>Excel Value</th><th>PDF Value</th><th>Severity</th>
<th>Message</th><th>Excel Source</th><th>PDF Source</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></body></html>"""


def write_error_report_files(compare_result: Any, *, output_dir: Path, basename: str | None = None) -> dict[str, str]:
    normalized = normalize_compare_result(compare_result)
    if normalized["matched"]:
        return {}
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = basename or normalized["request_no"] or "request_compare_error"
    safe_name = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in safe_name)
    json_path = output_dir / f"{safe_name}.json"
    csv_path = output_dir / f"{safe_name}.csv"
    html_path = output_dir / f"{safe_name}.html"
    json_path.write_bytes(build_error_report_json(compare_result) or b"")
    csv_path.write_bytes(build_error_report_csv(compare_result) or b"")
    html_path.write_text(build_error_report_html(compare_result), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "html": str(html_path)}
