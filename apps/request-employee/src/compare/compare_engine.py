from decimal import Decimal
from parser.normalizer import clean_text
from compare.line_matcher import LineMatcher
from compare.severity import classify_difference, money_equal

class CompareEngine:
    HEADER_FIELDS = ("request_no", "request_date", "customer_name", "subtotal", "tax_amount", "total_amount")
    LINE_FIELDS = ("product_code", "product_name", "quantity", "unit_price", "amount")
    MONEY_FIELDS = {"subtotal", "tax_amount", "total_amount", "quantity", "unit_price", "amount"}

    def __init__(self, money_tolerance="0"):
        self.money_tolerance = Decimal(str(money_tolerance))

    def compare(self, pdf_doc, excel_doc):
        diffs = []
        for field in self.HEADER_FIELDS:
            a, b = getattr(pdf_doc, field), getattr(excel_doc, field)
            if not self._equal(field, a, b):
                diffs.append(self._diff("header", field, a, b))

        for n, (p, e) in enumerate(LineMatcher().match(pdf_doc.lines, excel_doc.lines), 1):
            if p is None or e is None:
                diffs.append(self._diff(f"line:{n}", "line_presence", bool(p), bool(e)))
                continue
            key = p.product_code or p.product_name or str(n)
            for field in self.LINE_FIELDS:
                a, b = getattr(p, field), getattr(e, field)
                if not self._equal(field, a, b):
                    diffs.append(self._diff(f"line:{key}", field, a, b))
        return diffs

    def _equal(self, field, a, b):
        if field in self.MONEY_FIELDS:
            return money_equal(a, b, self.money_tolerance)
        return clean_text(a) == clean_text(b)

    def _diff(self, scope, field, pdf_value, excel_value):
        return {
            "scope": scope,
            "field": field,
            "pdf": str(pdf_value),
            "excel": str(excel_value),
            "severity": classify_difference(field, str(pdf_value), str(excel_value)),
            "status": "DIFFERENT",
        }
