from __future__ import annotations
import json

class RequestRepository:
    def save_bundle(self, conn, pdf_doc, excel_doc, diffs):
        try:
            pdf_id = self._save_request(conn, "PDF", pdf_doc)
            excel_id = self._save_request(conn, "EXCEL", excel_doc)
            self._save_differences(conn, pdf_doc.request_no or excel_doc.request_no, diffs)
            conn.commit()
            return {"pdf_id": pdf_id, "excel_id": excel_id}
        except Exception:
            conn.rollback()
            raise

    def save_request(self, conn, source: str, doc):
        try:
            request_id = self._save_request(conn, source, doc)
            conn.commit()
            return request_id
        except Exception:
            conn.rollback()
            raise

    def save_differences(self, conn, request_no: str, diffs: list[dict]):
        try:
            self._save_differences(conn, request_no, diffs)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _save_request(self, conn, source: str, doc):
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO request_header
                (request_no, request_date, customer_name, total_amount, source_file, source_type, raw_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    doc.request_no, doc.request_date or None, doc.customer_name,
                    str(doc.total_amount), doc.source_file, source,
                    json.dumps(doc.to_dict(), ensure_ascii=False),
                ),
            )
            request_id = cur.fetchone()[0]
            for line in doc.lines:
                cur.execute(
                    """
                    INSERT INTO request_line
                    (request_id, line_no, product_code, product_name, quantity, unit_price, amount, tax_rate)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        request_id, line.line_no, line.product_code, line.product_name,
                        str(line.quantity), str(line.unit_price), str(line.amount), str(line.tax_rate),
                    ),
                )
        return request_id

    def _save_differences(self, conn, request_no: str, diffs: list[dict]):
        with conn.cursor() as cur:
            for d in diffs:
                cur.execute(
                    """
                    INSERT INTO compare_result
                    (request_no, scope, field_name, pdf_value, excel_value, severity, status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        request_no, d.get("scope"), d.get("field"), d.get("pdf"),
                        d.get("excel"), d.get("severity"), d.get("status"),
                    ),
                )
