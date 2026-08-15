from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.request_batch_compare_import_service import (
    EXCEL_EXTENSIONS,
    PDF_EXTENSIONS,
    _extract_excel,
    _extract_pdf,
    _likely_customer,
    _pair_key,
    _pdf_recipient_name,
)
from src.services.request_folder_settings_service import standard_directories, validate_business_month
from src.services.tlc_access_control_service import ensure_schema as ensure_access_control_schema
from src.services.tlc_customer_master_service import (
    ensure_customer_master_table,
    normalize_customer_name,
    normalize_formal_name_unique_key,
    save_customer,
)
from src.services.tlc_customer_name_identity_service import (
    backfill_customer_names,
    match_name,
    register_name,
)

BATCH_TABLE = "tlc_customer_candidate_batch"
CANDIDATE_TABLE = "tlc_customer_import_candidate"
AUDIT_TABLE = "tlc_customer_candidate_audit"
MODULE_CODE = "CUSTOMER_CANDIDATE"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_candidate_name(value: str) -> str:
    # TLC_CUSTOMER_CANDIDATE_KABU_NORMALIZATION_R1
    result = unicodedata.normalize("NFKC", str(value or "")).strip()
    result = re.sub(r"\(\s*株\s*\)", "株式会社", result)
    result = re.sub(r"株\s*\)", "株式会社", result)
    result = re.sub(r"\(\s*株(?!式会社)", "株式会社", result)
    result = re.sub(r"[\s\u3000]+", " ", result)
    result = re.sub(r"\s*(御中|様|殿)\s*$", "", result).strip()
    return result


def ensure_schema(db: Session) -> None:
    ensure_access_control_schema(db)
    ensure_customer_master_table(db)
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {BATCH_TABLE}(
      id VARCHAR(64) PRIMARY KEY,business_month VARCHAR(6) NOT NULL,
      source_batch_id VARCHAR(64) NOT NULL DEFAULT '',source_directory TEXT NOT NULL DEFAULT '',
      operator VARCHAR(255) NOT NULL DEFAULT '',
      status VARCHAR(32) NOT NULL,source_rows INTEGER NOT NULL DEFAULT 0,
      candidate_count INTEGER NOT NULL DEFAULT 0,matched_count INTEGER NOT NULL DEFAULT 0,
      review_count INTEGER NOT NULL DEFAULT 0,conflict_count INTEGER NOT NULL DEFAULT 0,
      started_at VARCHAR(64) NOT NULL,completed_at VARCHAR(64) NOT NULL DEFAULT '',
      message TEXT NOT NULL DEFAULT '')"""))
    batch_columns = {str(row[1]) for row in db.execute(text(f"PRAGMA table_info({BATCH_TABLE})")).all()}
    if "source_directory" not in batch_columns:
        db.execute(text(f"ALTER TABLE {BATCH_TABLE} ADD COLUMN source_directory TEXT NOT NULL DEFAULT ''"))
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {CANDIDATE_TABLE}(
      id VARCHAR(64) PRIMARY KEY,candidate_batch_id VARCHAR(64) NOT NULL,
      business_month VARCHAR(6) NOT NULL,source_batch_id VARCHAR(64) NOT NULL,
      raw_customer_name VARCHAR(500) NOT NULL,normalized_customer_name VARCHAR(500) NOT NULL,
      suggested_formal_name VARCHAR(500) NOT NULL,source_count INTEGER NOT NULL DEFAULT 1,
      source_pair_keys TEXT NOT NULL DEFAULT '',matched_customer_id VARCHAR(64) NOT NULL DEFAULT '',
      matched_customer_code VARCHAR(128) NOT NULL DEFAULT '',matched_customer_name VARCHAR(500) NOT NULL DEFAULT '',
      match_type VARCHAR(64) NOT NULL DEFAULT '',match_score INTEGER NOT NULL DEFAULT 0,
      review_status VARCHAR(32) NOT NULL DEFAULT 'WAIT_REVIEW',resolution_action VARCHAR(32) NOT NULL DEFAULT '',
      reviewer VARCHAR(255) NOT NULL DEFAULT '',reviewed_at VARCHAR(64) NOT NULL DEFAULT '',
      review_comment TEXT NOT NULL DEFAULT '',imported_customer_id VARCHAR(64) NOT NULL DEFAULT '',
      created_at VARCHAR(64) NOT NULL,updated_at VARCHAR(64) NOT NULL,
      UNIQUE(candidate_batch_id,normalized_customer_name))"""))
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {AUDIT_TABLE}(
      id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id VARCHAR(64) NOT NULL DEFAULT '',
      actor VARCHAR(255) NOT NULL DEFAULT '',action VARCHAR(64) NOT NULL,
      detail TEXT NOT NULL DEFAULT '',created_at VARCHAR(64) NOT NULL)"""))
    db.execute(text("""INSERT OR IGNORE INTO tlc_permission_module
      (id,module_code,name_zh,active,sort_order,created_at,updated_at)
      VALUES(:id,:code,'客户候选提取与审核',1,36,:stamp,:stamp)"""),
      {"id": uuid4().hex, "code": MODULE_CODE, "stamp": now()})
    db.commit()


def _row(row: Any) -> dict[str, Any]:
    return dict(row._mapping if hasattr(row, "_mapping") else row)


def _customers(db: Session) -> list[dict[str, Any]]:
    return [_row(row) for row in db.execute(text("SELECT * FROM tlc_customer_master WHERE active=1")).all()]


def _match_customer(name: str, customers: list[dict[str, Any]]) -> dict[str, Any]:
    exact_key = normalize_formal_name_unique_key(name)
    loose_key = normalize_customer_name(name)
    for customer in customers:
        if normalize_formal_name_unique_key(customer.get("formal_name", "")) == exact_key:
            return {"customer": customer, "type": "FORMAL_NAME_EXACT", "score": 100}
    fields = ("delivery_name_1", "delivery_name_2")
    for customer in customers:
        for field in fields:
            value = str(customer.get(field, "") or "")
            if value and normalize_customer_name(value) == loose_key:
                return {"customer": customer, "type": field.upper(), "score": 95}
    return {"customer": {}, "type": "", "score": 0}


def _match_customer_identity(db: Session, name: str, customers: list[dict[str, Any]]) -> dict[str, Any]:
    backfill_customer_names(db)
    identity = match_name(db, name)
    if identity.get("match_status") == "MATCHED":
        customer = next((row for row in customers if row.get("id") == identity["customer_record_id"]), {})
        return {"customer": customer, "type": "NAME_IDENTITY_" + identity["name_type"], "score": 100}
    return _match_customer(name, customers)


def _incoming_directory(business_month: str) -> Path:
    month = validate_business_month(business_month)
    incoming = standard_directories()["incoming"] / month
    if not incoming.is_dir():
        raise ValueError(f"Request Incoming directory was not found: {incoming}")
    return incoming


def _file_candidates(incoming: Path) -> tuple[list[dict[str, str]], list[str], int]:
    files = sorted(
        path for path in incoming.iterdir()
        if path.is_file() and path.suffix.lower() in (PDF_EXTENSIONS | EXCEL_EXTENSIONS)
    )
    groups: dict[str, dict[str, list[Path]]] = {}
    for path in files:
        group = groups.setdefault(_pair_key(path), {"pdf": [], "excel": []})
        group["pdf" if path.suffix.lower() in PDF_EXTENSIONS else "excel"].append(path)
    candidates: list[dict[str, str]] = []
    errors: list[str] = []
    for pair_key, group in sorted(groups.items()):
        pdf_path = group["pdf"][0] if group["pdf"] else None
        excel_path = group["excel"][0] if group["excel"] else None
        name = ""
        extraction_failed = False
        try:
            if pdf_path:
                name = _pdf_recipient_name(_extract_pdf(pdf_path))
            if not name and excel_path:
                name = _likely_customer(_extract_excel(excel_path))
        except Exception as exc:
            errors.append(f"{pair_key}: {exc}")
            extraction_failed = True
        sources = [path.name for path in (pdf_path, excel_path) if path]
        if name:
            candidates.append({"name": name, "pair_key": pair_key, "sources": " | ".join(sources)})
        elif sources and not extraction_failed:
            errors.append(f"{pair_key}: recipient customer name was not found ({' | '.join(sources)})")
    return candidates, errors, len(groups)


def run_extraction(db: Session, business_month: str, source_batch_id: str = "", operator: str = "") -> dict[str, Any]:
    ensure_schema(db)
    month = validate_business_month(str(business_month or ""))
    incoming = _incoming_directory(month)
    source_rows, extraction_errors, scanned_pairs = _file_candidates(incoming)
    grouped: dict[str, dict[str, Any]] = {}
    for row in source_rows:
        raw = str(row["name"] or "").strip()
        formal = normalize_candidate_name(raw)
        key = normalize_formal_name_unique_key(formal)
        if not key:
            continue
        item = grouped.setdefault(key, {"raw": raw, "formal": formal, "pairs": [], "sources": []})
        item["pairs"].append(str(row["pair_key"] or ""))
        item["sources"].append(str(row["sources"] or ""))

    batch_id = uuid4().hex
    stamp = now()
    customers = _customers(db)
    matched = review = 0
    db.execute(text(f"""INSERT INTO {BATCH_TABLE}(id,business_month,source_batch_id,operator,status,
      source_directory,source_rows,candidate_count,matched_count,review_count,conflict_count,started_at,completed_at,message)
      VALUES(:id,:month,:source,:operator,'RUNNING',:directory,:rows,0,0,0,0,:stamp,'','')"""),
      {"id": batch_id, "month": month, "source": "", "operator": operator.strip(),
       "directory": str(incoming),
       "rows": scanned_pairs, "stamp": stamp})
    for key, item in grouped.items():
        match = _match_customer_identity(db, item["formal"], customers)
        customer = match["customer"]
        status = "MATCHED" if customer else "WAIT_REVIEW"
        matched += 1 if customer else 0
        review += 0 if customer else 1
        db.execute(text(f"""INSERT INTO {CANDIDATE_TABLE}(id,candidate_batch_id,business_month,
          source_batch_id,raw_customer_name,normalized_customer_name,suggested_formal_name,source_count,
          source_pair_keys,matched_customer_id,matched_customer_code,matched_customer_name,match_type,
          match_score,review_status,created_at,updated_at)
          VALUES(:id,:candidate_batch,:month,:source,:raw,:normalized,:formal,:count,:pairs,:matched_id,
          :matched_code,:matched_name,:match_type,:score,:status,:stamp,:stamp)"""), {
            "id": uuid4().hex, "candidate_batch": batch_id, "month": month, "source": "",
            "raw": item["raw"], "normalized": key, "formal": item["formal"],
            "count": len(item["pairs"]), "pairs": "\n".join(item["sources"][:100]),
            "matched_id": customer.get("id", ""), "matched_code": customer.get("customer_id", ""),
            "matched_name": customer.get("formal_name", ""), "match_type": match["type"],
            "score": match["score"], "status": status, "stamp": stamp,
        })
    status = "COMPLETED_WITH_ERRORS" if extraction_errors else "COMPLETED"
    message = f"pairs={scanned_pairs}, candidates={len(grouped)}, errors={len(extraction_errors)}"
    if extraction_errors:
        message += "\n" + "\n".join(extraction_errors[:50])
    db.execute(text(f"""UPDATE {BATCH_TABLE} SET status=:status,candidate_count=:c,
      matched_count=:m,review_count=:r,conflict_count=:errors,completed_at=:stamp,message=:message
      WHERE id=:id"""), {"status": status, "c": len(grouped), "m": matched, "r": review,
      "errors": len(extraction_errors), "stamp": now(), "message": message, "id": batch_id})
    db.commit()
    return get_batch(db, batch_id)


def get_batch(db: Session, batch_id: str) -> dict[str, Any]:
    ensure_schema(db)
    row = db.execute(text(f"SELECT * FROM {BATCH_TABLE} WHERE id=:id"), {"id": batch_id}).first()
    if not row:
        raise LookupError("Customer candidate Batch was not found")
    return _row(row)


def latest_batch(db: Session, business_month: str = "") -> dict[str, Any]:
    ensure_schema(db)
    params: dict[str, Any] = {}
    where = ""
    if business_month:
        where = "WHERE business_month=:month"
        params["month"] = re.sub(r"\D", "", business_month)
    row = db.execute(text(f"SELECT * FROM {BATCH_TABLE} {where} ORDER BY started_at DESC,rowid DESC LIMIT 1"), params).first()
    return _row(row) if row else {}


def list_candidates(db: Session, business_month: str = "", status: str = "", batch_id: str = "", limit: int = 1000) -> list[dict[str, Any]]:
    ensure_schema(db)
    clauses, params = [], {"limit": min(max(int(limit), 1), 5000)}
    if business_month:
        clauses.append("business_month=:month"); params["month"] = re.sub(r"\D", "", business_month)
    if status:
        clauses.append("review_status=:status"); params["status"] = status.strip().upper()
    if batch_id:
        clauses.append("candidate_batch_id=:batch"); params["batch"] = batch_id.strip()
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return [_row(row) for row in db.execute(text(f"SELECT * FROM {CANDIDATE_TABLE} {where} ORDER BY created_at DESC,id LIMIT :limit"), params).all()]


def resolve_candidate(db: Session, candidate_id: str, action: str, reviewer: str, comment: str = "", customer_id: str = "", formal_name: str = "") -> dict[str, Any]:
    ensure_schema(db)
    row = db.execute(text(f"SELECT * FROM {CANDIDATE_TABLE} WHERE id=:id"), {"id": candidate_id}).first()
    if not row:
        raise LookupError("Customer candidate was not found")
    candidate = _row(row)
    action = str(action or "").strip().upper()
    imported_id = ""
    matched_id = candidate.get("matched_customer_id", "")
    matched_code = candidate.get("matched_customer_code", "")
    matched_name = candidate.get("matched_customer_name", "")
    if action == "LINK_EXISTING":
        target = db.execute(text("SELECT id,customer_id,formal_name FROM tlc_customer_master WHERE id=:id OR customer_id=:id LIMIT 1"), {"id": customer_id.strip() or matched_id}).first()
        if not target:
            raise ValueError("Existing customer was not found")
        matched_id, matched_code, matched_name = target
        status = "IMPORTED"
        imported_id = str(matched_id)
        register_name(db, customer_record_id=str(matched_id), customer_id=str(matched_code),
                      name_value=candidate["raw_customer_name"], name_type="REQUEST_NAME",
                      source_system="REQUEST_CUSTOMER_CANDIDATE", actor=reviewer)
    elif action == "CREATE_NEW":
        code = customer_id.strip() or ("CUST-CAND-" + uuid4().hex[:10].upper())
        name = formal_name.strip() or candidate["suggested_formal_name"]
        created = save_customer(db, {"customer_id": code, "formal_name": name,
                                    "source_system": "REQUEST_CUSTOMER_CANDIDATE",
                                    "note": "Created from request customer candidate"})
        imported_id, matched_id = created["id"], created["id"]
        matched_code, matched_name = created["customer_id"], created["formal_name"]
        register_name(db, customer_record_id=created["id"], customer_id=created["customer_id"],
                      name_value=created["formal_name"], name_type="FORMAL",
                      source_system="REQUEST_CUSTOMER_CANDIDATE", actor=reviewer)
        if normalize_identity_name := candidate.get("raw_customer_name"):
            register_name(db, customer_record_id=created["id"], customer_id=created["customer_id"],
                          name_value=normalize_identity_name, name_type="REQUEST_NAME",
                          source_system="REQUEST_CUSTOMER_CANDIDATE", actor=reviewer)
        status = "IMPORTED"
    elif action == "REJECT":
        status = "REJECTED"
    elif action == "HOLD":
        status = "ON_HOLD"
    else:
        raise ValueError("action must be LINK_EXISTING, CREATE_NEW, REJECT, or HOLD")
    stamp = now()
    db.execute(text(f"""UPDATE {CANDIDATE_TABLE} SET matched_customer_id=:matched_id,
      matched_customer_code=:matched_code,matched_customer_name=:matched_name,review_status=:status,
      resolution_action=:action,reviewer=:reviewer,reviewed_at=:stamp,review_comment=:comment,
      imported_customer_id=:imported,updated_at=:stamp WHERE id=:id"""), {
        "matched_id": matched_id, "matched_code": matched_code, "matched_name": matched_name,
        "status": status, "action": action, "reviewer": reviewer.strip(), "stamp": stamp,
        "comment": comment.strip(), "imported": imported_id, "id": candidate_id,
    })
    db.execute(text(f"INSERT INTO {AUDIT_TABLE}(candidate_id,actor,action,detail,created_at) VALUES(:id,:actor,:action,:detail,:stamp)"),
               {"id": candidate_id, "actor": reviewer.strip(), "action": action, "detail": comment.strip(), "stamp": stamp})
    db.commit()
    return _row(
        db.execute(
            text(f"SELECT * FROM {CANDIDATE_TABLE} WHERE id=:id"),
            {"id": candidate_id},
        ).one()
    )


def bulk_resolve_candidates(
    db: Session,
    candidate_ids: list[str],
    action: str,
    reviewer: str,
    comment: str = "",
    formal_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    ids = list(dict.fromkeys(str(value or "").strip() for value in candidate_ids))
    ids = [value for value in ids if value]
    if not ids:
        raise ValueError("At least one customer candidate must be selected")
    if len(ids) > 1000:
        raise ValueError("A maximum of 1000 candidates can be processed at once")
    if not str(reviewer or "").strip():
        raise ValueError("Operator is required")
    action = str(action or "").strip().upper()
    succeeded: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    formal_names = formal_names or {}
    for candidate_id in ids:
        try:
            current = db.execute(
                text(f"SELECT * FROM {CANDIDATE_TABLE} WHERE id=:id"),
                {"id": candidate_id},
            ).first()
            if not current:
                raise LookupError("Customer candidate was not found")
            candidate = _row(current)
            customer_id = ""
            formal_name = str(formal_names.get(candidate_id) or candidate.get("suggested_formal_name", "")).strip()
            if action == "LINK_EXISTING":
                customer_id = candidate.get("matched_customer_id", "") or candidate.get("matched_customer_code", "")
                if not customer_id:
                    raise ValueError("No automatically matched customer is available")
            resolved = resolve_candidate(
                db,
                candidate_id,
                action,
                reviewer,
                comment,
                customer_id,
                formal_name,
            )
            succeeded.append({"id": candidate_id, "name": str(resolved.get("suggested_formal_name") or "")})
        except Exception as exc:
            db.rollback()
            failed.append({
                "id": candidate_id,
                "name": str(candidate.get("suggested_formal_name") or "") if "candidate" in locals() else "",
                "message": str(exc),
            })
        finally:
            if "candidate" in locals():
                del candidate
    return {
        "requested": len(ids),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "success_items": succeeded,
        "failure_items": failed[:20],
    }


def export_csv(records: list[dict[str, Any]]) -> bytes:
    fields = ["id", "candidate_batch_id", "business_month", "raw_customer_name", "suggested_formal_name",
              "source_count", "matched_customer_code", "matched_customer_name", "match_type", "match_score",
              "review_status", "resolution_action", "review_comment"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue().encode("utf-8-sig")


def import_csv(db: Session, raw: bytes, actor: str) -> dict[str, Any]:
    ensure_schema(db)
    text_value = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text_value))
    updated, errors = 0, []
    for row_no, row in enumerate(reader, 2):
        candidate_id = str(row.get("id") or "").strip()
        if not candidate_id:
            errors.append({"row": row_no, "message": "id is required"}); continue
        result = db.execute(text(f"""UPDATE {CANDIDATE_TABLE} SET suggested_formal_name=:formal,
          resolution_action=:action,review_comment=:comment,reviewer=:actor,updated_at=:stamp WHERE id=:id"""), {
            "formal": str(row.get("suggested_formal_name") or "").strip(),
            "action": str(row.get("resolution_action") or "").strip().upper(),
            "comment": str(row.get("review_comment") or "").strip(), "actor": actor.strip(),
            "stamp": now(), "id": candidate_id,
        })
        if result.rowcount: updated += 1
        else: errors.append({"row": row_no, "message": "candidate not found"})
    db.commit()
    return {"updated": updated, "errors": errors}
