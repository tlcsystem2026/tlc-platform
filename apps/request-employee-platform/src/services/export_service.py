from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
from typing import Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.responses import Response


def _filename(prefix: str, ext: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in prefix)
    return f"{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"


def _xml_text(value) -> str:
    return escape("" if value is None else str(value))


def export_xlsx(rows: Sequence[Mapping], filename_prefix: str) -> Response:
    rows = list(rows)
    columns = list(rows[0].keys()) if rows else ["message"]
    data = rows or [{"message": "no data"}]

    def cell(ref: str, value) -> str:
        return f'<c r="{ref}" t="inlineStr"><is><t>{_xml_text(value)}</t></is></c>'

    def col_name(n: int) -> str:
        s = ""
        while n:
            n, rem = divmod(n - 1, 26)
            s = chr(65 + rem) + s
        return s

    sheet_rows = []
    header = "".join(cell(f"{col_name(i+1)}1", c) for i, c in enumerate(columns))
    sheet_rows.append(f'<row r="1">{header}</row>')
    for r_idx, row in enumerate(data, start=2):
        cells = "".join(cell(f"{col_name(i+1)}{r_idx}", row.get(c, "")) for i, c in enumerate(columns))
        sheet_rows.append(f'<row r="{r_idx}">{cells}</row>')

    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetData>' + "".join(sheet_rows) + '</sheetData></worksheet>')

    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>')
        z.writestr("_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
        z.writestr("xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Results" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", sheet)

    return Response(
        out.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{_filename(filename_prefix, "xlsx")}"'},
    )


def export_pdf(rows: Sequence[Mapping], filename_prefix: str, title: str) -> Response:
    # Minimal valid PDF for portable smoke-safe delivery. Business PDF layout will be upgraded
    # at the milestone package after confirming server fonts and reportlab availability.
    rows = list(rows)
    columns = list(rows[0].keys()) if rows else ["message"]
    data = rows or [{"message": "no data"}]
    lines = [title, f"Generated: {datetime.now().isoformat(timespec='seconds')}",
             " | ".join(columns)]
    lines += [" | ".join(str(row.get(c, "")) for c in columns) for row in data[:80]]

    def pdf_escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    y = 800
    commands = ["BT", "/F1 8 Tf"]
    for line in lines:
        ascii_line = line.encode("ascii", "replace").decode("ascii")
        commands += [f"40 {y} Td ({pdf_escape(ascii_line[:120])}) Tj", f"-40 {-12} Td"]
        y -= 12
        if y < 40:
            break
    commands.append("ET")
    stream = "\n".join(commands).encode("ascii")

    objs = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>")
    objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objs, 1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(pdf)
    pdf += f"xref\n0 {len(objs)+1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += f"trailer << /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()

    return Response(
        bytes(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_filename(filename_prefix, "pdf")}"'},
    )
