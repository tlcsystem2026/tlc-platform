from __future__ import annotations
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Any

@dataclass
class RequestLine:
    line_no: int
    product_code: str = ""
    product_name: str = ""
    quantity: Decimal = Decimal("0")
    unit_price: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("quantity", "unit_price", "amount", "tax_rate"):
            d[k] = str(d[k])
        return d

@dataclass
class RequestDocument:
    request_no: str = ""
    request_date: str = ""
    customer_name: str = ""
    subtotal: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")
    lines: list[RequestLine] = field(default_factory=list)
    source_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_no": self.request_no,
            "request_date": self.request_date,
            "customer_name": self.customer_name,
            "subtotal": str(self.subtotal),
            "tax_amount": str(self.tax_amount),
            "total_amount": str(self.total_amount),
            "source_file": self.source_file,
            "lines": [x.to_dict() for x in self.lines],
        }
