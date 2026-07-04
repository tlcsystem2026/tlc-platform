from pathlib import Path
from html import escape

def write_html_report(diffs: list[dict], output_path: str | Path, title="Request Difference Report"):
    rows = []
    for d in diffs:
        sev = escape(d.get("severity", "INFO"))
        rows.append(
            "<tr>"
            f"<td>{escape(d.get('scope',''))}</td>"
            f"<td>{escape(d.get('field',''))}</td>"
            f"<td>{escape(d.get('pdf',''))}</td>"
            f"<td>{escape(d.get('excel',''))}</td>"
            f"<td class='{sev.lower()}'>{sev}</td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{escape(title)}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; }}
th {{ background: #f3f3f3; }}
.error {{ color: #b00020; font-weight: bold; }}
.warning {{ color: #9a6700; font-weight: bold; }}
.info {{ color: #333; }}
</style>
</head>
<body>
<h1>{escape(title)}</h1>
<p>Difference count: {len(diffs)}</p>
<table>
<thead><tr><th>Scope</th><th>Field</th><th>PDF</th><th>Excel</th><th>Severity</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</body>
</html>"""
    Path(output_path).write_text(html, encoding="utf-8")
