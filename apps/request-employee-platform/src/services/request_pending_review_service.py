from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.services.tlc_customer_master_service import ensure_customer_master_table

TABLE_NAME = "request_pending_review"

def ensure_pending_review_table(db: Session) -> None:
    db.execute(text(f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id VARCHAR(64) PRIMARY KEY,
        request_no VARCHAR(255) NOT NULL UNIQUE,
        request_date VARCHAR(64) NOT NULL DEFAULT '',
        customer_id VARCHAR(255) NOT NULL DEFAULT '',
        customer_name VARCHAR(500) NOT NULL DEFAULT '',
        currency VARCHAR(16) NOT NULL DEFAULT '',
        subtotal VARCHAR(64) NOT NULL DEFAULT '',
        tax_amount VARCHAR(64) NOT NULL DEFAULT '',
        total_amount VARCHAR(64) NOT NULL DEFAULT '',
        excel_source VARCHAR(1000) NOT NULL DEFAULT '',
        pdf_source VARCHAR(1000) NOT NULL DEFAULT '',
        compare_summary TEXT NOT NULL DEFAULT '{{}}',
        request_payload TEXT NOT NULL DEFAULT '{{}}',
        status VARCHAR(64) NOT NULL DEFAULT 'PENDING_REVIEW',
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    )"""))
    columns={row[1] for row in db.execute(text(f"PRAGMA table_info({TABLE_NAME})")).all()}
    additions={
      "file_review_id":"VARCHAR(64) NOT NULL DEFAULT ''",
      "batch_id":"VARCHAR(64) NOT NULL DEFAULT ''",
      "batch_item_id":"VARCHAR(64) NOT NULL DEFAULT ''",
      "business_month":"VARCHAR(6) NOT NULL DEFAULT ''",
      "source_request_no":"VARCHAR(255) NOT NULL DEFAULT ''",
      "file_review_status":"VARCHAR(64) NOT NULL DEFAULT ''",
      "reviewed_by":"VARCHAR(255) NOT NULL DEFAULT ''",
      "review_note":"TEXT NOT NULL DEFAULT ''",
      "reviewed_at":"VARCHAR(64) NOT NULL DEFAULT ''",
      "sales_ledger_id":"VARCHAR(64) NOT NULL DEFAULT ''",
      "posted_at":"VARCHAR(64) NOT NULL DEFAULT ''",
      "taxable_amount_10":"VARCHAR(64) NOT NULL DEFAULT ''",
      "tax_amount_10":"VARCHAR(64) NOT NULL DEFAULT ''",
      "tax_inclusive_amount_10":"VARCHAR(64) NOT NULL DEFAULT ''",
      "taxable_amount_8":"VARCHAR(64) NOT NULL DEFAULT ''",
      "tax_amount_8":"VARCHAR(64) NOT NULL DEFAULT ''",
      "tax_inclusive_amount_8":"VARCHAR(64) NOT NULL DEFAULT ''",
      "non_taxable_amount":"VARCHAR(64) NOT NULL DEFAULT ''",
      "tax_exempt_amount":"VARCHAR(64) NOT NULL DEFAULT ''",
      "pdf_tax_breakdown_json":"TEXT NOT NULL DEFAULT '{}'",
      "excel_tax_breakdown_json":"TEXT NOT NULL DEFAULT '{}'",
    }
    for column,definition in additions.items():
        if column not in columns:
            db.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {column} {definition}"))
    db.commit()

def _row_to_dict(row: Any) -> dict[str, Any]:
    result = dict(row._mapping if hasattr(row, "_mapping") else row)
    for key in ("compare_summary", "request_payload"):
        try: result[key] = json.loads(result.get(key) or "{}")
        except Exception: result[key] = {}
    return result

def create_pending_review(db: Session, payload: dict[str, Any], *, commit: bool = True) -> dict[str, Any]:
    ensure_pending_review_table(db)
    if not bool(payload.get("matched",False)):
        raise ValueError("Only file-reviewed request documents can enter business review")
    source_request_no=str(payload.get("request_no","") or "").strip()
    if not source_request_no: raise ValueError("request_no is required")
    file_review_id=str(payload.get("file_review_id","") or "").strip()
    if file_review_id:
        existing=db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE file_review_id=:v"),{"v":file_review_id}).first()
        if existing:return {"status":"exists","record":_row_to_dict(existing)}
    internal_no=source_request_no
    collision=db.execute(text(f"SELECT id FROM {TABLE_NAME} WHERE request_no=:v"),{"v":internal_no}).first()
    if collision: internal_no=f"{source_request_no}#FR-{(file_review_id or uuid4().hex)[:8]}"
    doc=payload.get("request_document") or {}; sources=payload.get("sources") or {}; now=datetime.now(timezone.utc).isoformat()
    p={
      "id":uuid4().hex,"request_no":internal_no,"request_date":str(doc.get("request_date","") or ""),
      "customer_id":str(doc.get("customer_id","") or ""),"customer_name":str(doc.get("customer_name","") or ""),
      "currency":str(doc.get("currency","JPY") or "JPY"),"subtotal":str(doc.get("subtotal","") or ""),
      "tax_amount":str(doc.get("tax_amount","") or ""),"total_amount":str(doc.get("total_amount","") or ""),
      "excel_source":str(sources.get("excel","") or ""),"pdf_source":str(sources.get("pdf","") or ""),
      "compare_summary":json.dumps({"matched":True,"difference_count":0,"file_review_status":"FILE_REVIEWED_OK"},ensure_ascii=False),
      "request_payload":json.dumps(doc,ensure_ascii=False),"status":"PENDING_REVIEW","created_at":now,"updated_at":now,
      "file_review_id":file_review_id,"batch_id":str(payload.get("batch_id","") or ""),
      "batch_item_id":str(payload.get("batch_item_id","") or ""),"business_month":str(payload.get("business_month","") or ""),
      "source_request_no":source_request_no,"file_review_status":"FILE_REVIEWED_OK",
      "taxable_amount_10":str(doc.get("taxable_amount_10","") or ""),
      "tax_amount_10":str(doc.get("tax_amount_10","") or ""),
      "tax_inclusive_amount_10":str(doc.get("tax_inclusive_amount_10","") or ""),
      "taxable_amount_8":str(doc.get("taxable_amount_8","") or ""),
      "tax_amount_8":str(doc.get("tax_amount_8","") or ""),
      "tax_inclusive_amount_8":str(doc.get("tax_inclusive_amount_8","") or ""),
      "non_taxable_amount":str(doc.get("non_taxable_amount","") or ""),
      "tax_exempt_amount":str(doc.get("tax_exempt_amount","") or ""),
      "pdf_tax_breakdown_json":str(doc.get("pdf_tax_breakdown_json","{}") or "{}"),
      "excel_tax_breakdown_json":str(doc.get("excel_tax_breakdown_json","{}") or "{}"),
    }
    db.execute(text(f"""INSERT INTO {TABLE_NAME}(
      id,request_no,request_date,customer_id,customer_name,currency,
      subtotal,tax_amount,total_amount,excel_source,pdf_source,
      compare_summary,request_payload,status,created_at,updated_at,
      file_review_id,batch_id,batch_item_id,business_month,
      source_request_no,file_review_status,
      taxable_amount_10,tax_amount_10,tax_inclusive_amount_10,
      taxable_amount_8,tax_amount_8,tax_inclusive_amount_8,
      non_taxable_amount,tax_exempt_amount,
      pdf_tax_breakdown_json,excel_tax_breakdown_json
    ) VALUES(
      :id,:request_no,:request_date,:customer_id,:customer_name,:currency,
      :subtotal,:tax_amount,:total_amount,:excel_source,:pdf_source,
      :compare_summary,:request_payload,:status,:created_at,:updated_at,
      :file_review_id,:batch_id,:batch_item_id,:business_month,
      :source_request_no,:file_review_status,
      :taxable_amount_10,:tax_amount_10,:tax_inclusive_amount_10,
      :taxable_amount_8,:tax_amount_8,:tax_inclusive_amount_8,
      :non_taxable_amount,:tax_exempt_amount,
      :pdf_tax_breakdown_json,:excel_tax_breakdown_json
    )"""),p)
    if commit: db.commit()
    row=db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id"),{"id":p["id"]}).first()
    return {"status":"created","record":_row_to_dict(row)}

def list_pending_reviews(
    db: Session,
    *,
    status: str = "",
    keyword: str = "",
    customer_id: str = "",
    customer_name: str = "",
    limit: int = 0,
) -> list[dict[str, Any]]:
    ensure_pending_review_table(db)
    ensure_customer_master_table(db)
    requested_limit = int(limit or 0)
    clauses: list[str] = []
    params: dict[str, Any] = {}
    limit_sql = ""
    if requested_limit > 0:
        params["limit"] = requested_limit
        limit_sql = " LIMIT :limit"
    if status:
        clauses.append("p.status=:status")
        params["status"] = status
    if customer_id:
        clauses.append("p.customer_id LIKE :customer_id")
        params["customer_id"] = f"%{customer_id}%"
    if customer_name:
        clauses.append("""(
          p.customer_name LIKE :customer_name OR
          c.formal_name LIKE :customer_name OR
          c.hiragana_name LIKE :customer_name OR
          c.katakana_name LIKE :customer_name OR
          c.katakana_name_short LIKE :customer_name OR
          c.short_name LIKE :customer_name OR
          c.delivery_name_1 LIKE :customer_name OR
          c.delivery_name_2 LIKE :customer_name OR
          c.alias_1 LIKE :customer_name OR c.alias_2 LIKE :customer_name OR
          c.alias_3 LIKE :customer_name OR c.alias_4 LIKE :customer_name OR
          c.alias_5 LIKE :customer_name
        )""")
        params["customer_name"] = f"%{customer_name}%"
    if keyword:
        searchable = [
            "p.id", "p.request_no", "p.source_request_no", "p.request_date",
            "p.customer_id", "p.customer_name", "p.currency", "p.subtotal",
            "p.tax_amount", "p.total_amount", "p.excel_source", "p.pdf_source",
            "p.compare_summary", "p.request_payload", "p.status",
            "p.created_at", "p.updated_at", "p.file_review_id", "p.batch_id",
            "p.batch_item_id", "p.business_month", "p.file_review_status",
            "p.reviewed_by", "p.review_note", "p.sales_ledger_id",
            "p.reviewed_at", "p.posted_at",
            "p.taxable_amount_10", "p.tax_amount_10",
            "p.tax_inclusive_amount_10", "p.taxable_amount_8",
            "p.tax_amount_8", "p.tax_inclusive_amount_8",
            "p.non_taxable_amount", "p.tax_exempt_amount",
            "c.customer_id", "c.formal_name", "c.hiragana_name",
            "c.katakana_name", "c.katakana_name_short", "c.short_name",
            "c.delivery_name_1", "c.delivery_name_2", "c.postal_code",
            "c.address_1", "c.address_2", "c.phone_number", "c.email_address",
            "c.jis_municipality_code", "c.shipper_code",
            "c.alias_1", "c.alias_2", "c.alias_3", "c.alias_4", "c.alias_5",
            "c.status_code", "c.note", "c.source_system",
        ]
        clauses.append("(" + " OR ".join(
            f"CAST({column} AS TEXT) LIKE :keyword" for column in searchable
        ) + ")")
        params["keyword"] = f"%{keyword}%"
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    rows = db.execute(text(f"""
      SELECT p.*,
             c.formal_name AS master_formal_name,
             c.hiragana_name AS master_hiragana_name,
             c.katakana_name AS master_katakana_name,
             c.katakana_name_short AS master_katakana_name_short,
             c.short_name AS master_short_name,
             c.delivery_name_1 AS master_delivery_name_1,
             c.delivery_name_2 AS master_delivery_name_2,
             c.alias_1 AS master_alias_1,
             c.alias_2 AS master_alias_2,
             c.alias_3 AS master_alias_3,
             c.alias_4 AS master_alias_4,
             c.alias_5 AS master_alias_5
      FROM {TABLE_NAME} p
      LEFT JOIN tlc_customer_master c ON c.customer_id=p.customer_id
      {where}
      ORDER BY p.created_at DESC
      {limit_sql}
    """), params).all()
    return [_row_to_dict(row) for row in rows]

def get_pending_review(db: Session, record_id: str) -> dict[str, Any] | None:
    ensure_pending_review_table(db)
    row = db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id"), {"id": record_id}).first()
    return _row_to_dict(row) if row else None
