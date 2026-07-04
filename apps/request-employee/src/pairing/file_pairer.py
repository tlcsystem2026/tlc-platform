from __future__ import annotations
from pathlib import Path
import re
from difflib import SequenceMatcher

INVOICE_RE = re.compile(r"(LY\d{4,})", re.I)

class FilePairer:
    def pair(self, pdf_dir: str | Path, excel_dir: str | Path) -> list[dict]:
        pdfs = sorted(Path(pdf_dir).glob("*.pdf"))
        excels = sorted(Path(excel_dir).glob("*.xlsx"))
        excel_pool = list(excels)
        results = []

        for pdf in pdfs:
            match = self._best_match(pdf, excel_pool)
            if match:
                excel_pool.remove(match["excel"])
                results.append({
                    "pdf": str(pdf),
                    "excel": str(match["excel"]),
                    "score": match["score"],
                    "method": match["method"],
                    "status": "PAIRED",
                })
            else:
                results.append({
                    "pdf": str(pdf),
                    "excel": "",
                    "score": 0,
                    "method": "",
                    "status": "MISSING_EXCEL",
                })

        for excel in excel_pool:
            results.append({
                "pdf": "",
                "excel": str(excel),
                "score": 0,
                "method": "",
                "status": "MISSING_PDF",
            })
        return results

    def _best_match(self, pdf: Path, excels: list[Path]) -> dict | None:
        pdf_invoice = self._invoice(pdf.name)
        if pdf_invoice:
            for excel in excels:
                if self._invoice(excel.name) == pdf_invoice:
                    return {"excel": excel, "score": 100, "method": "invoice_no"}

        best = None
        for excel in excels:
            score = int(SequenceMatcher(None, pdf.stem, excel.stem).ratio() * 100)
            if best is None or score > best["score"]:
                best = {"excel": excel, "score": score, "method": "filename_similarity"}

        if best and best["score"] >= 70:
            return best
        return None

    def _invoice(self, name: str) -> str:
        m = INVOICE_RE.search(name)
        return m.group(1).upper() if m else ""
