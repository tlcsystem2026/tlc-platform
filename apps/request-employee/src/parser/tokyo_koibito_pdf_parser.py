from __future__ import annotations
import re
from decimal import Decimal
from pathlib import Path

from parser.pdf_parser import PDFParser
from parser.normalizer import clean_text, normalize_money
from models.request import RequestDocument, RequestLine

class TokyoKoibitoPDFParser(PDFParser):
    """
    Tokyo Koibito invoice/request PDF parser.

    Build011 improvement:
    - more tolerant total amount extraction
    - more tolerant customer extraction
    - keeps simple text-line item extraction
    """

    def parse(self, path: str | Path) -> RequestDocument:
        path = Path(path)
        text = self.extract_text(path)
        doc = RequestDocument(source_file=str(path))
        doc.request_no = self._request_no(text)
        doc.request_date = self._request_date(text)
        doc.customer_name = self._customer(text)
        doc.total_amount = self._total(text)
        doc.lines = self._line_items_from_text(text)
        doc.subtotal, doc.tax_amount = self._sum_subtotal_tax(text)
        return doc

    def _request_no(self, text: str) -> str:
        m = re.search(r"請求書番号\s*(LY\d+)", text)
        if m:
            return m.group(1)
        m = re.search(r"\b(LY\d{4,})\b", text)
        return m.group(1) if m else ""

    def _request_date(self, text: str) -> str:
        m = re.search(r"請求日\s*(\d{4})年(\d{1,2})月(\d{1,2})日", text)
        if not m:
            m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
        if not m:
            return ""
        y, mo, d = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"

    def _customer(self, text: str) -> str:
        for line in text.splitlines():
            s = clean_text(line)
            if "御中" in s and not s.startswith("毎度"):
                return s.replace("御中", "").strip()
        return ""

    def _total(self, text: str) -> Decimal:
        candidates = re.findall(r"(?:ご請求額|請求額|合計).*?[¥￥]?\s*([\d,]+)", text)
        if candidates:
            return normalize_money(candidates[-1])
        amounts = re.findall(r"[¥￥]\s*([\d,]+)", text)
        return normalize_money(amounts[-1]) if amounts else Decimal("0")

    def _sum_subtotal_tax(self, text: str):
        subtotals = [normalize_money(x) for x in re.findall(r"小計（税抜）\s*[¥￥\\]?\s*([\d,]+)", text)]
        taxes = [normalize_money(x) for x in re.findall(r"消費税\s*(?:8|10)%\s*[¥￥\\]?\s*([\d,]+)", text)]
        return sum(subtotals, Decimal("0")), sum(taxes, Decimal("0"))

    def _line_items_from_text(self, text: str) -> list[RequestLine]:
        rows = []
        current_tax = Decimal("0.10")
        for raw in text.splitlines():
            s = clean_text(raw)
            if "②軽減税率商品" in s:
                current_tax = Decimal("0.08")
                continue
            if "①通常税率商品" in s:
                current_tax = Decimal("0.10")
                continue
            if not re.match(r"^\d+\s+", s):
                continue
            parts = s.split()
            if len(parts) < 5:
                continue
            try:
                line_no = int(parts[0])
            except ValueError:
                continue
            amount = normalize_money(parts[-1])
            unit_price = normalize_money(parts[-2])
            quantity = normalize_money(parts[-3])
            if amount == 0 and unit_price == 0 and quantity == 0:
                continue
            name_parts = parts[1:-3]
            product_code = ""
            for token in name_parts:
                if re.search(r"\d{8,}", token):
                    product_code = token
                    break
            rows.append(RequestLine(
                line_no=line_no,
                product_code=product_code,
                product_name=" ".join(name_parts),
                quantity=quantity,
                unit_price=unit_price,
                amount=amount,
                tax_rate=current_tax,
            ))
        return rows
