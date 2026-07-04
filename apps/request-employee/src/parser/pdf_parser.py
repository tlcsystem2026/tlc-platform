from __future__ import annotations
from pathlib import Path
import re
import pdfplumber

from models.request import RequestDocument, RequestLine
from parser.normalizer import clean_text, normalize_money

class PDFParser:
    REQUEST_NO_PATTERNS = [
        r"(?:請求書番号|請求番号|No\.?)\s*[:：]?\s*(LY\d+)",
        r"\b(LY\d{4,})\b",
    ]
    DATE_PATTERNS = [
        r"(\d{4})[年/\-.](\d{1,2})[月/\-.](\d{1,2})日?",
    ]

    def extract_text(self, path: str | Path) -> str:
        chunks = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                chunks.append(page.extract_text(x_tolerance=2, y_tolerance=3) or "")
        return "\n".join(chunks)

    def parse(self, path: str | Path) -> RequestDocument:
        path = Path(path)
        text = self.extract_text(path)
        doc = RequestDocument(source_file=str(path))
        doc.request_no = self._request_no(text)
        doc.request_date = self._date(text)
        doc.customer_name = self._customer(text)
        doc.total_amount = self._label_money(text, ["合計金額", "ご請求金額", "請求金額", "合計"])
        doc.tax_amount = self._label_money(text, ["消費税", "税額"])
        doc.subtotal = self._label_money(text, ["小計", "税抜合計"])
        doc.lines = self._lines(path)
        return doc

    def _request_no(self, text: str) -> str:
        for p in self.REQUEST_NO_PATTERNS:
            m = re.search(p, text, re.I)
            if m:
                return clean_text(m.group(1))
        return ""

    def _date(self, text: str) -> str:
        for p in self.DATE_PATTERNS:
            m = re.search(p, text)
            if m:
                y, mo, d = map(int, m.groups())
                return f"{y:04d}-{mo:02d}-{d:02d}"
        return ""

    def _customer(self, text: str) -> str:
        for line in text.splitlines():
            s = clean_text(line)
            if re.search(r"(株式会社|合同会社|有限会社).*(御中|様)?$", s):
                return re.sub(r"(御中|様)$", "", s).strip()
        return ""

    def _label_money(self, text: str, labels: list[str]):
        for label in labels:
            m = re.search(rf"{re.escape(label)}\s*[:：]?\s*[¥￥]?\s*([\d,]+(?:\.\d+)?)", text)
            if m:
                return normalize_money(m.group(1))
        return normalize_money(0)

    def _lines(self, path: Path) -> list[RequestLine]:
        result = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    result.extend(self._table_lines(table, len(result)))
        return result

    def _table_lines(self, table, offset: int) -> list[RequestLine]:
        if not table or len(table) < 2:
            return []
        header = [clean_text(x) for x in table[0]]
        def idx(names):
            for i, h in enumerate(header):
                if any(n in h for n in names):
                    return i
            return None
        name_i = idx(["商品名", "品名", "摘要"])
        qty_i = idx(["数量", "個数"])
        price_i = idx(["単価"])
        amount_i = idx(["金額"])
        code_i = idx(["商品コード", "品番", "コード"])
        if name_i is None or amount_i is None:
            return []
        rows = []
        for raw in table[1:]:
            if not raw or name_i >= len(raw):
                continue
            name = clean_text(raw[name_i])
            if not name or any(x in name for x in ["小計", "合計", "消費税"]):
                continue
            get = lambda i: raw[i] if i is not None and i < len(raw) else ""
            rows.append(RequestLine(
                line_no=offset + len(rows) + 1,
                product_code=clean_text(get(code_i)),
                product_name=name,
                quantity=normalize_money(get(qty_i)),
                unit_price=normalize_money(get(price_i)),
                amount=normalize_money(get(amount_i)),
            ))
        return rows
