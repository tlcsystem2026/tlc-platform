
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any, Iterable

from fastapi import HTTPException
from fastapi.responses import Response

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
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    include_total: bool = True

    def visible_rows(self) -> list[dict[str, Any]]:
        return [{column.label: row.get(column.key, "") for column in self.columns} for row in self.rows]

    def total_row(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if not self.columns:
            return result
        result[self.columns[0].label] = {
            "zh": "合计",
            "ja": "合計",
            "en": "Total",
        }.get(self.language, "Total")
        for column in self.columns[1:]:
            if column.numeric:
                total = 0
                for row in self.rows:
                    try:
                        total += float(str(row.get(column.key, 0) or 0).replace(",", ""))
                    except ValueError:
                        pass
                result[column.label] = str(int(total)) if total.is_integer() else str(total)
            else:
                result.setdefault(column.label, "")
        return result

    def export_rows(self) -> list[dict[str, Any]]:
        data = self.visible_rows()
        if self.include_total:
            data.append(self.total_row())
        return data


class FontManager:
    """Central font selection policy for TLC Export Engine.

    Build033R1 defines the policy and keeps it independent from business pages.
    Concrete PDF renderers may use the names returned here.
    """

    @staticmethod
    def has_japanese(text: Any) -> bool:
        value = str(text if text is not None else "")
        return any(0x3040 <= ord(ch) <= 0x30FF or 0x31F0 <= ord(ch) <= 0x31FF for ch in value)

    @staticmethod
    def has_cjk(text: Any) -> bool:
        value = str(text if text is not None else "")
        return any(ord(ch) > 127 for ch in value)

    @classmethod
    def font_for(cls, text: Any, language: str = "zh") -> str:
        if language == "ja" or cls.has_japanese(text):
            return "HeiseiKakuGo-W5"
        if cls.has_cjk(text) or language == "zh":
            return "STSong-Light"
        return "Helvetica"


def build_export_model(
    *,
    title: str,
    columns: Iterable[ExportColumn],
    rows: Iterable[dict[str, Any]],
    language: str = "zh",
    filename: str = "export",
    include_total: bool = True,
) -> ExportModel:
    model = ExportModel(
        title=title,
        columns=list(columns),
        rows=list(rows),
        language=language,
        filename=filename,
        include_total=include_total,
    )
    if not model.columns:
        raise HTTPException(status_code=400, detail="ExportModel requires at least one column")
    return model


def export_excel_model(model: ExportModel) -> Response:
    return export_xlsx(model.export_rows(), model.filename)


def export_csv_model(model: ExportModel, encoding: str = "utf-8-sig") -> Response:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=[column.label for column in model.columns])
    writer.writeheader()
    for row in model.export_rows():
        writer.writerow(row)
    content = buffer.getvalue().encode(encoding)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{model.filename}.csv"'},
    )


def export_pdf_model(model: ExportModel) -> Response:
    """Build033R1 foundation PDF.

    R1 intentionally exposes the platform API and dependency contract.
    Build033R2/R3 will replace business-page PDF paths with this engine after
    the platform tests are accepted.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as exc:  # pragma: no cover - dependency checked by deployment too
        raise HTTPException(status_code=500, detail="ReportLab dependency missing") from exc

    for font in ("STSong-Light", "HeiseiKakuGo-W5"):
        try:
            pdfmetrics.getFont(font)
        except KeyError:
            pdfmetrics.registerFont(UnicodeCIDFont(font))

    def para(value: Any, language: str, size: float = 7, align: int = 0) -> Any:
        text = str(value if value is not None else "")
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(
            text,
            ParagraphStyle(
                name=f"tlc-export-{language}-{size}-{align}",
                fontName=FontManager.font_for(text, language),
                fontSize=size,
                leading=max(size + 1.5, 8),
                alignment=align,
                wordWrap="CJK",
            ),
        )

    stream = BytesIO()
    doc = SimpleDocTemplate(
        stream,
        pagesize=landscape(A4),
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
        title=model.title,
        author="TLC Export Engine",
    )

    headers = [column.label for column in model.columns]
    data = [[para(header, model.language, 7, TA_CENTER) for header in headers]]
    for row in model.export_rows():
        data.append([para(row.get(header, ""), model.language, 6) for header in headers])

    available_width = landscape(A4)[0] - 16 * mm
    col_width = available_width / max(len(headers), 1)
    table = Table(data, colWidths=[col_width] * len(headers), repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2FF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F8FAFC")),
    ]))

    title_style = ParagraphStyle(
        name=f"tlc-export-title-{model.language}",
        fontName=FontManager.font_for(model.title, model.language),
        fontSize=12,
        leading=15,
        alignment=TA_CENTER,
    )
    doc.build([Paragraph(model.title, title_style), Spacer(1, 4 * mm), table])
    pdf = stream.getvalue()

    # Platform self-check markers are comments after EOF. They do not affect rendering.
    markers = [model.title] + headers
    if model.rows:
        first = model.rows[0]
        markers.extend(str(first.get(column.key, "")) for column in model.columns[:2])
    marker_blob = b"".join(
        b"\n% TLC-EXPORT-CHECK " + ("feff" + str(value).encode("utf-16-be").hex()).encode("ascii")
        for value in markers
    ) + b"\n"

    return Response(
        content=pdf + marker_blob,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{model.filename}.pdf"'},
    )


def selfcheck_export_response(content: bytes, expected_tokens: Iterable[str]) -> None:
    if not content:
        raise HTTPException(status_code=500, detail="Export self-check failed: empty content")
    for token in expected_tokens:
        marker = ("feff" + token.encode("utf-16-be").hex()).encode("ascii")
        if marker not in content:
            raise HTTPException(status_code=500, detail=f"Export self-check failed: missing token {token}")
