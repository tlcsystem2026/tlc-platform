from __future__ import annotations
from pathlib import Path
from decimal import Decimal
import re
from openpyxl import load_workbook

from models.request import RequestDocument, RequestLine
from parser.normalizer import clean_text, normalize_money

class TokyoKoibitoExcelParser:
    """
    Tokyo Koibito Excel parser.

    Strategy:
    - Read all cells in the active worksheet
    - Detect known labels: 請求日 / 請求書番号 / 御中 / ご請求額
    - Detect line rows by pattern: line number + item + qty + price + amount
    """

    def parse(self, path: str | Path) -> RequestDocument:
        path = Path(path)
        wb = load_workbook(path, data_only=True)
        ws = wb.active
        cells = [[c.value for c in row] for row in ws.iter_rows()]
        flat = [clean_text(v) for row in cells for v in row if v not in (None, "")]

        doc = RequestDocument(source_file=str(path))
        joined = " ".join(flat)

        doc.request_no = self._request_no(joined)
        doc.request_date = self._request_date(joined)
        doc.customer_name = self._customer(flat)
        doc.total_amount = self._total(joined)
        doc.lines = self._lines(cells)
        if not doc.total_amount:
            doc.total_amount = sum((x.amount for x in doc.lines), Decimal("0"))
        return doc

    def _request_no(self, text: str) -> str:
        m = re.search(r"(LY\d{4,})", text)
        return m.group(1) if m else ""

    def _request_date(self, text: str) -> str:
        m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
        if not m:
            return ""
        y, mo, d = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"

    def _customer(self, flat: list[str]) -> str:
        for value in flat:
            if value.endswith("御中"):
                return value.removesuffix("御中").strip()
        return ""

    def _total(self, text: str):
        m = re.search(r"ご請求額.*?([\d,]{3,})", text)
        return normalize_money(m.group(1)) if m else Decimal("0")

    def _lines(self, cells) -> list[RequestLine]:
        results = []
        tax_rate = Decimal("0.10")
        for row in cells:
            row_text = " ".join(clean_text(v) for v in row if v not in (None, ""))
            if "②軽減税率商品" in row_text:
                tax_rate = Decimal("0.08")
                continue
            if "①通常税率商品" in row_text:
                tax_rate = Decimal("0.10")
                continue
            values = [v for v in row if v not in (None, "")]
            if len(values) < 5:
                continue
            if not str(values[0]).strip().isdigit():
                continue
            # Try numeric columns from the end.
            line_no = int(values[0])
            amount = normalize_money(values[-1])
            unit_price = normalize_money(values[-2])
            qty = normalize_money(values[-3])
            name_values = [clean_text(v) for v in values[1:-3]]
            product_name = " ".join(name_values)
            product_code = ""
            for token in name_values:
                if re.search(r"\d{8,}", token):
                    product_code = token
                    break
            if product_name and amount:
                results.append(RequestLine(
                    line_no=line_no,
                    product_code=product_code,
                    product_name=product_name,
                    quantity=qty,
                    unit_price=unit_price,
                    amount=amount,
                    tax_rate=tax_rate,
                ))
        return results
