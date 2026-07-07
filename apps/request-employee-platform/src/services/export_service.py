from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
from typing import Mapping, Sequence

from fastapi.responses import Response


def _safe_filename(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in name)


def export_excel_html(rows: Sequence[Mapping], filename_prefix: str) -> Response:
    safe_rows = list(rows) if rows else [{"message": "no data"}]
    columns = list(safe_rows[0].keys())
    html = [
        "<html><head><meta charset='utf-8'></head><body><table border='1'>",
        "<tr>" + "".join(f"<th>{escape(str(c))}</th>" for c in columns) + "</tr>",
    ]
    for row in safe_rows:
        html.append("<tr>" + "".join(f"<td>{escape(str(row.get(c, '')))}</td>" for c in columns) + "</tr>")
    html.append("</table></body></html>")
    filename = _safe_filename(f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls")
    return Response(
        content="\n".join(html).encode("utf-8-sig"),
        media_type="application/vnd.ms-excel",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def export_text_pdf(rows: Sequence[Mapping], filename_prefix: str, title: str) -> Response:
    # Minimal PDF for first delivery. Later builds can replace this with reportlab/weasyprint.
    safe_rows = list(rows) if rows else [{"message": "no data"}]
    columns = list(safe_rows[0].keys())
    lines = [title, f"Generated: {datetime.now().isoformat(timespec='seconds')}", "", " | ".join(columns), "-" * 100]
    for row in safe_rows:
        lines.append(" | ".join(str(row.get(c, "")) for c in columns))
    text = "\n".join(lines)[:3500]
    pdf_text = "BT /F1 9 Tf 40 800 Td (" + text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").replace("\n", ") Tj T* (") + ") Tj ET"
    data = pdf_text.encode("latin-1", errors="replace")
    stream = BytesIO()
    stream.write(b"%PDF-1.4\n")
    stream.write(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    stream.write(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    stream.write(b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents 4 0 R >> endobj\n")
    stream.write(f"4 0 obj << /Length {len(data)} >> stream\n".encode())
    stream.write(data)
    stream.write(b"\nendstream endobj\ntrailer << /Root 1 0 R >>\n%%EOF")
    filename = _safe_filename(f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    return Response(
        content=stream.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
