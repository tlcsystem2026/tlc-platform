from openpyxl import Workbook

def export_diff(rows, output):
    wb=Workbook()
    ws=wb.active
    ws.append(["Field","PDF","Excel"])
    for r in rows:
        ws.append([r.get("field"),r.get("pdf"),r.get("excel")])
    wb.save(output)
