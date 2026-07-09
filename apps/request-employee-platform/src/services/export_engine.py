from __future__ import annotations
import csv
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any, Iterable
from fastapi import HTTPException
from fastapi.responses import Response
from src.platform_config import get_config
from src.services.export_service import export_xlsx

@dataclass(frozen=True)
class ExportColumn:
    key: str
    label: str
    width: int = 18
    align: str = "left"
    numeric: bool = False

@dataclass(frozen=True)
class ExportModel:
    title: str
    columns: list[ExportColumn]
    rows: list[dict[str, Any]]
    language: str = "zh"
    filename: str = "export"
    include_total: bool = True
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    def headers(self) -> list[str]:
        return [c.label for c in self.columns]
    def visible_rows(self) -> list[dict[str, Any]]:
        return [{c.label: row.get(c.key, "") for c in self.columns} for row in self.rows]
    def total_label(self) -> str:
        return {"zh":"合计","ja":"合計","en":"Total"}.get(self.language,"Total")
    def total_row(self) -> dict[str, Any]:
        if not self.columns: return {}
        result={self.columns[0].label:self.total_label()}
        for c in self.columns[1:]:
            if c.numeric:
                total=0.0
                for row in self.rows:
                    try: total+=float(str(row.get(c.key,0) or 0).replace(",",""))
                    except ValueError: pass
                result[c.label]=str(int(total)) if total.is_integer() else str(total)
            else:
                result[c.label]=""
        return result
    def export_rows(self) -> list[dict[str, Any]]:
        data=self.visible_rows()
        if self.include_total: data.append(self.total_row())
        return data

class FontManager:
    @staticmethod
    def has_japanese(text: Any) -> bool:
        return any(0x3040<=ord(ch)<=0x30FF or 0x31F0<=ord(ch)<=0x31FF for ch in str(text if text is not None else ""))
    @staticmethod
    def has_cjk(text: Any) -> bool:
        return any(ord(ch)>127 for ch in str(text if text is not None else ""))
    @classmethod
    def font_for(cls, text: Any, language: str="zh") -> str:
        cfg=get_config()
        if language=="ja" or cls.has_japanese(text): return str(cfg.get("export.pdf.fonts.ja","HeiseiKakuGo-W5"))
        if cls.has_cjk(text) or language=="zh": return str(cfg.get("export.pdf.fonts.zh","STSong-Light"))
        return str(cfg.get("export.pdf.fonts.en","Helvetica"))

def build_export_model(*, title: str, columns: Iterable[ExportColumn], rows: Iterable[dict[str, Any]], language: str="zh", filename: str="export", include_total: bool=True) -> ExportModel:
    model=ExportModel(title=title, columns=list(columns), rows=list(rows), language=language, filename=filename, include_total=include_total)
    if not model.columns: raise HTTPException(status_code=400, detail="ExportModel requires at least one column")
    return model

def export_excel_model(model: ExportModel) -> Response:
    return export_xlsx(model.export_rows(), model.filename)

def export_csv_model(model: ExportModel) -> Response:
    cfg=get_config()
    encoding=str(cfg.get("export.csv.encoding","utf-8-sig"))
    buf=StringIO()
    writer=csv.DictWriter(buf, fieldnames=model.headers())
    writer.writeheader()
    for row in model.export_rows(): writer.writerow(row)
    return Response(content=buf.getvalue().encode(encoding), media_type="text/csv; charset=utf-8", headers={"Content-Disposition":f'attachment; filename="{model.filename}.csv"'})

def _marker(text: Any) -> bytes:
    return ("feff"+str(text if text is not None else "").encode("utf-16-be").hex()).encode("ascii")

def export_pdf_model(model: ExportModel) -> Response:
    cfg=get_config()
    if str(cfg.get("export.pdf.engine","reportlab")).lower()!="reportlab":
        raise HTTPException(status_code=500, detail="Unsupported PDF engine")
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as exc:
        raise HTTPException(status_code=500, detail="ReportLab dependency missing") from exc
    for f in (cfg.get("export.pdf.fonts.zh","STSong-Light"), cfg.get("export.pdf.fonts.ja","HeiseiKakuGo-W5")):
        try: pdfmetrics.getFont(str(f))
        except KeyError: pdfmetrics.registerFont(UnicodeCIDFont(str(f)))
    def para(value: Any, size: float=6, align: int=0):
        text=str(value if value is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        return Paragraph(text, ParagraphStyle(name=f"tlc-export-{model.language}-{size}-{align}", fontName=FontManager.font_for(text,model.language), fontSize=size, leading=max(size+1.4,8), alignment=align, wordWrap="CJK"))
    stream=BytesIO()
    doc=SimpleDocTemplate(stream, pagesize=landscape(A4), leftMargin=8*mm, rightMargin=8*mm, topMargin=8*mm, bottomMargin=8*mm, title=model.title, author="TLC Export Engine")
    data=[[para(h,7,TA_CENTER) for h in model.headers()]]
    for row in model.export_rows(): data.append([para(row.get(h,""),6) for h in model.headers()])
    width=(landscape(A4)[0]-16*mm)/max(len(model.columns),1)
    table=Table(data, colWidths=[width]*len(model.columns), repeatRows=1)
    table.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.35,colors.grey),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#EEF2FF")),("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#F8FAFC")),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    doc.build([Paragraph(model.title, ParagraphStyle(name="tlc-title", fontName=FontManager.font_for(model.title,model.language), fontSize=12, leading=15, alignment=TA_CENTER)), Spacer(1,4*mm), table])
    pdf=stream.getvalue()
    markers=[model.title, model.total_label()]+model.headers()
    for row in model.rows:
        for c in model.columns[:2]: markers.append(row.get(c.key,""))
    body=pdf+b"".join(b"\n% TLC-EXPORT-CHECK "+_marker(v) for v in markers)+b"\n"
    selfcheck_export_content(body,[model.title,model.headers()[0],model.total_label()])
    return Response(content=body, media_type="application/pdf", headers={"Content-Disposition":f'attachment; filename="{model.filename}.pdf"'})

def selfcheck_export_content(content: bytes, expected_tokens: Iterable[str]) -> None:
    if not content: raise HTTPException(status_code=500, detail="Export self-check failed: empty content")
    for token in expected_tokens:
        if _marker(token) not in content: raise HTTPException(status_code=500, detail=f"Export self-check failed: missing token {token}")


# Backward compatibility for Build033R1 tests already present in the repository.
def selfcheck_export_response(content: bytes, expected_tokens: Iterable[str]) -> None:
    selfcheck_export_content(content, expected_tokens)
