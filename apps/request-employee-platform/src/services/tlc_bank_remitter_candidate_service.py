from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from src.services.multi_bank_csv_import_service import (
    detect_bank_csv,
    ensure_bank_transaction_table,
    parse_bank_csv,
)
from src.services.tlc_customer_name_matching_service import (
    match_customer_name,
    normalize_customer_name,
)
from src.services.tlc_customer_master_service import ensure_customer_master_table
from src.services.tlc_customer_name_identity_service import register_name


MARKER = "TLC_BANK_REMITTER_CANDIDATE_BATCH_R1"
CSV_MARKER = "TLC_BANK_REMITTER_CANDIDATE_FROM_CSV_R1"
CSV_REVIEW_MARKER = "TLC_BANK_REMITTER_CANDIDATE_CSV_REVIEW_R1"
BATCH_TABLE = "tlc_bank_remitter_candidate_batch"
CANDIDATE_TABLE = "tlc_bank_remitter_candidate"
AUDIT_TABLE = "tlc_bank_remitter_candidate_audit"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema(db: Session) -> None:
    ensure_bank_transaction_table(db)
    ensure_customer_master_table(db)
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {BATCH_TABLE}(
      id VARCHAR(64) PRIMARY KEY,business_month VARCHAR(6) NOT NULL,operator VARCHAR(255) NOT NULL DEFAULT '',
      status VARCHAR(32) NOT NULL,transaction_count INTEGER NOT NULL DEFAULT 0,candidate_count INTEGER NOT NULL DEFAULT 0,
      matched_count INTEGER NOT NULL DEFAULT 0,review_count INTEGER NOT NULL DEFAULT 0,started_at VARCHAR(64) NOT NULL,
      completed_at VARCHAR(64) NOT NULL DEFAULT '',message TEXT NOT NULL DEFAULT '',
      bank_code VARCHAR(64) NOT NULL DEFAULT '',source_name VARCHAR(1000) NOT NULL DEFAULT '')"""))
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {CANDIDATE_TABLE}(
      id VARCHAR(64) PRIMARY KEY,candidate_batch_id VARCHAR(64) NOT NULL,business_month VARCHAR(6) NOT NULL,
      raw_remitter_name VARCHAR(500) NOT NULL,normalized_remitter_name VARCHAR(500) NOT NULL,
      transaction_count INTEGER NOT NULL DEFAULT 0,total_amount VARCHAR(64) NOT NULL DEFAULT '0',
      first_transaction_date VARCHAR(32) NOT NULL DEFAULT '',last_transaction_date VARCHAR(32) NOT NULL DEFAULT '',
      bank_codes TEXT NOT NULL DEFAULT '',matched_customer_id VARCHAR(255) NOT NULL DEFAULT '',
      matched_customer_name VARCHAR(500) NOT NULL DEFAULT '',match_status VARCHAR(32) NOT NULL DEFAULT 'WAIT_REVIEW',
      match_level VARCHAR(64) NOT NULL DEFAULT '',review_status VARCHAR(32) NOT NULL DEFAULT 'WAIT_REVIEW',
      resolution_action VARCHAR(32) NOT NULL DEFAULT '',name_identity_field VARCHAR(32) NOT NULL DEFAULT '',
      reviewer VARCHAR(255) NOT NULL DEFAULT '',review_comment TEXT NOT NULL DEFAULT '',reviewed_at VARCHAR(64) NOT NULL DEFAULT '',
      created_at VARCHAR(64) NOT NULL,updated_at VARCHAR(64) NOT NULL,
      UNIQUE(candidate_batch_id,normalized_remitter_name))"""))
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {AUDIT_TABLE}(
      id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id VARCHAR(64) NOT NULL,actor VARCHAR(255) NOT NULL DEFAULT '',
      action VARCHAR(64) NOT NULL,detail TEXT NOT NULL DEFAULT '',created_at VARCHAR(64) NOT NULL)"""))
    columns = {column["name"] for column in inspect(db.bind).get_columns(BATCH_TABLE)}
    if "bank_code" not in columns:
        db.execute(text(f"ALTER TABLE {BATCH_TABLE} ADD COLUMN bank_code VARCHAR(64) NOT NULL DEFAULT ''"))
    if "source_name" not in columns:
        db.execute(text(f"ALTER TABLE {BATCH_TABLE} ADD COLUMN source_name VARCHAR(1000) NOT NULL DEFAULT ''"))
    db.commit()


def _row(value: Any) -> dict[str, Any]:
    return dict(value._mapping if hasattr(value, "_mapping") else value)


def _month(value: str) -> str:
    result = "".join(character for character in str(value or "") if character.isdigit())
    if len(result) != 6:
        raise ValueError("business_month must be YYYYMM")
    return result


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0").replace(",", ""))
    except InvalidOperation:
        return Decimal("0")


def run_extraction(db: Session, business_month: str, operator: str = "") -> dict[str, Any]:
    ensure_schema(db)
    month = _month(business_month)
    rows = db.execute(text("""SELECT counterparty,amount,transaction_date,bank_code
      FROM bank_transaction_import
      WHERE direction='CREDIT' AND counterparty<>'' AND replace(substr(transaction_date,1,7),'-','')=:month
      ORDER BY transaction_date,id"""), {"month": month}).all()
    grouped: dict[str, dict[str, Any]] = {}
    for source in rows:
        item = _row(source)
        raw = str(item.get("counterparty") or "").strip()
        normalized = normalize_customer_name(raw)
        if not normalized:
            continue
        target = grouped.setdefault(normalized, {
            "raw": raw, "count": 0, "total": Decimal("0"), "dates": [], "banks": set()
        })
        target["count"] += 1
        target["total"] += _decimal(item.get("amount"))
        if item.get("transaction_date"):
            target["dates"].append(str(item["transaction_date"]))
        if item.get("bank_code"):
            target["banks"].add(str(item["bank_code"]))
    batch_id, stamp = uuid4().hex, now()
    db.execute(text(f"""INSERT INTO {BATCH_TABLE}(id,business_month,operator,status,transaction_count,
      candidate_count,matched_count,review_count,started_at,completed_at,message)
      VALUES(:id,:month,:operator,'RUNNING',:transactions,0,0,0,:stamp,'','')"""), {
        "id": batch_id, "month": month, "operator": str(operator or "").strip(),
        "transactions": len(rows), "stamp": stamp,
    })
    matched = review = 0
    for normalized, item in grouped.items():
        match = match_customer_name(db, raw_name=item["raw"], operator=operator, save_result=False)
        is_matched = match["match_status"] == "MATCHED"
        matched += int(is_matched)
        review += int(not is_matched)
        dates = sorted(item["dates"])
        db.execute(text(f"""INSERT INTO {CANDIDATE_TABLE}(id,candidate_batch_id,business_month,
          raw_remitter_name,normalized_remitter_name,transaction_count,total_amount,first_transaction_date,
          last_transaction_date,bank_codes,matched_customer_id,matched_customer_name,match_status,match_level,
          review_status,created_at,updated_at)
          VALUES(:id,:batch,:month,:raw,:normalized,:count,:total,:first,:last,:banks,:customer,:customer_name,
          :match_status,:level,:review_status,:stamp,:stamp)"""), {
            "id": uuid4().hex, "batch": batch_id, "month": month, "raw": item["raw"],
            "normalized": normalized, "count": item["count"], "total": format(item["total"], "f"),
            "first": dates[0] if dates else "", "last": dates[-1] if dates else "",
            "banks": ",".join(sorted(item["banks"])), "customer": match.get("customer_id", ""),
            "customer_name": match.get("customer_name", ""), "match_status": match["match_status"],
            "level": match.get("match_level", ""), "review_status": "AUTO_MATCHED" if is_matched else "WAIT_REVIEW",
            "stamp": stamp,
        })
    db.execute(text(f"""UPDATE {BATCH_TABLE} SET status='COMPLETED',candidate_count=:c,matched_count=:m,
      review_count=:r,completed_at=:stamp,message=:message WHERE id=:id"""), {
        "c": len(grouped), "m": matched, "r": review, "stamp": now(), "id": batch_id,
        "message": f"transactions={len(rows)}, remitters={len(grouped)}",
    })
    db.commit()
    return get_batch(db, batch_id)


def run_extraction_from_csv(
    db: Session,
    content: bytes,
    selected_bank_code: str,
    source_name: str,
    operator: str = "",
) -> dict[str, Any]:
    """Extract remitter candidates directly from an original bank CSV.

    This deliberately does not write to bank_transaction_import.
    """
    ensure_schema(db)
    selected = str(selected_bank_code or "").strip().upper()
    if not selected:
        raise ValueError("selected_bank_code is required")
    detected = detect_bank_csv(content)
    if detected != selected:
        raise ValueError(
            "Selected bank does not match CSV format: "
            f"selected={selected}, detected={detected}"
        )
    parsed = parse_bank_csv(
        content,
        source_file=str(source_name or "bank.csv"),
        import_batch_id="candidate-preview-" + uuid4().hex,
    )
    credits = [row for row in parsed if row.direction == "CREDIT" and row.counterparty.strip()]
    grouped: dict[str, dict[str, Any]] = {}
    for transaction in credits:
        raw = transaction.counterparty.strip()
        normalized = normalize_customer_name(raw)
        if not normalized:
            continue
        target = grouped.setdefault(normalized, {
            "raw": raw, "count": 0, "total": Decimal("0"), "dates": [], "banks": set()
        })
        target["count"] += 1
        target["total"] += _decimal(transaction.amount)
        if transaction.transaction_date:
            target["dates"].append(transaction.transaction_date)
        target["banks"].add(detected)

    batch_id, stamp = uuid4().hex, now()
    db.execute(text(f"""INSERT INTO {BATCH_TABLE}(id,business_month,operator,status,transaction_count,
      candidate_count,matched_count,review_count,started_at,completed_at,message,bank_code,source_name)
      VALUES(:id,'',:operator,'RUNNING',:transactions,0,0,0,:stamp,'','',:bank,:source)"""), {
        "id": batch_id, "operator": str(operator or "").strip(), "transactions": len(credits),
        "stamp": stamp, "bank": detected, "source": str(source_name or "bank.csv"),
    })
    matched = review = 0
    for normalized, item in grouped.items():
        match = match_customer_name(db, raw_name=item["raw"], operator=operator, save_result=False)
        is_matched = match["match_status"] == "MATCHED"
        matched += int(is_matched); review += int(not is_matched)
        dates = sorted(item["dates"])
        db.execute(text(f"""INSERT INTO {CANDIDATE_TABLE}(id,candidate_batch_id,business_month,
          raw_remitter_name,normalized_remitter_name,transaction_count,total_amount,first_transaction_date,
          last_transaction_date,bank_codes,matched_customer_id,matched_customer_name,match_status,match_level,
          review_status,created_at,updated_at)
          VALUES(:id,:batch,'',:raw,:normalized,:count,:total,:first,:last,:banks,:customer,:customer_name,
          :match_status,:level,:review_status,:stamp,:stamp)"""), {
            "id": uuid4().hex, "batch": batch_id, "raw": item["raw"], "normalized": normalized,
            "count": item["count"], "total": format(item["total"], "f"),
            "first": dates[0] if dates else "", "last": dates[-1] if dates else "",
            "banks": detected, "customer": match.get("customer_id", ""),
            "customer_name": match.get("customer_name", ""), "match_status": match["match_status"],
            "level": match.get("match_level", ""),
            "review_status": "AUTO_MATCHED" if is_matched else "WAIT_REVIEW", "stamp": stamp,
        })
    db.execute(text(f"""UPDATE {BATCH_TABLE} SET status='COMPLETED',candidate_count=:c,
      matched_count=:m,review_count=:r,completed_at=:stamp,message=:message WHERE id=:id"""), {
        "c": len(grouped), "m": matched, "r": review, "stamp": now(), "id": batch_id,
        "message": f"source_rows={len(parsed)}, credit_rows={len(credits)}, remitters={len(grouped)}",
    })
    db.commit()
    return get_batch(db, batch_id)


def get_batch(db: Session, batch_id: str) -> dict[str, Any]:
    ensure_schema(db)
    row = db.execute(text(f"SELECT * FROM {BATCH_TABLE} WHERE id=:id"), {"id": batch_id}).first()
    if not row:
        raise LookupError("Bank remitter candidate Batch was not found")
    return _row(row)


def latest_batch(db: Session, business_month: str = "", bank_code: str = "") -> dict[str, Any]:
    ensure_schema(db)
    where, params = "", {}
    if business_month:
        where, params = "WHERE business_month=:month", {"month": _month(business_month)}
    if bank_code:
        where = (where + " AND " if where else "WHERE ") + "bank_code=:bank"
        params["bank"] = str(bank_code).strip().upper()
    row = db.execute(text(f"SELECT * FROM {BATCH_TABLE} {where} ORDER BY started_at DESC,rowid DESC LIMIT 1"), params).first()
    return _row(row) if row else {}


def list_candidates(db: Session, business_month: str = "", status: str = "", batch_id: str = "", limit: int = 5000) -> list[dict[str, Any]]:
    ensure_schema(db)
    requested_limit = int(limit)
    clauses, params = [], {}
    if business_month:
        clauses.append("business_month=:month"); params["month"] = _month(business_month)
    if status:
        clauses.append("review_status=:status"); params["status"] = str(status).strip().upper()
    if batch_id:
        clauses.append("candidate_batch_id=:batch"); params["batch"] = str(batch_id).strip()
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    limit_sql = ""
    if requested_limit > 0:
        params["limit"] = min(requested_limit, 10000)
        limit_sql = " LIMIT :limit"
    rows = [_row(row) for row in db.execute(
        text(f"SELECT * FROM {CANDIDATE_TABLE} {where} ORDER BY created_at DESC,id{limit_sql}"),
        params,
    ).all()]
    # TLC_BANK_REMITTER_ASSIGNED_CUSTOMER_NAME_R1
    # The candidate table keeps the review-time snapshot.  Display the current
    # customer master formal name when the selected customer still exists.
    customer_keys = sorted({
        str(row.get("matched_customer_id") or "").strip()
        for row in rows if str(row.get("matched_customer_id") or "").strip()
    })
    if customer_keys and inspect(db.get_bind()).has_table("tlc_customer_master"):
        customer_lookup = {}
        for offset in range(0, len(customer_keys), 400):
            chunk = customer_keys[offset:offset + 400]
            key_params = {f"key_{index}": value for index, value in enumerate(chunk)}
            placeholders = ",".join(f":key_{index}" for index in range(len(chunk)))
            customer_rows = db.execute(text(
                "SELECT id,customer_id,formal_name FROM tlc_customer_master "
                f"WHERE id IN ({placeholders}) OR customer_id IN ({placeholders})"
            ), key_params).all()
            for customer_row in customer_rows:
                customer = _row(customer_row)
                formal_name = str(customer.get("formal_name") or "").strip()
                customer_lookup[str(customer.get("id") or "")] = formal_name
                customer_lookup[str(customer.get("customer_id") or "")] = formal_name
        for row in rows:
            current_name = customer_lookup.get(str(row.get("matched_customer_id") or "").strip(), "")
            if current_name:
                row["matched_customer_name"] = current_name
    return rows


def export_review_csv(records: list[dict[str, Any]]) -> bytes:
    """Export candidates with the editable offline-review columns.

    Identity and source columns are included for validation on import.  Only
    matched_customer_id, resolution_action and review_comment are writable.
    """
    fields = [
        "id", "candidate_batch_id", "bank_codes", "raw_remitter_name",
        "normalized_remitter_name", "transaction_count", "total_amount",
        "first_transaction_date", "last_transaction_date", "match_status",
        "matched_customer_id", "matched_customer_name", "review_status",
        "resolution_action", "review_comment",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue().encode("utf-8-sig")


def import_review_csv(db: Session, raw: bytes, actor: str) -> dict[str, Any]:
    """Validate the entire review CSV, then atomically store review drafts."""
    ensure_schema(db)
    reviewer = str(actor or "").strip()
    if not reviewer:
        raise ValueError("operator is required")
    content = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    required = {"id", "candidate_batch_id", "bank_codes", "matched_customer_id", "resolution_action", "review_comment"}
    headers = set(reader.fieldnames or [])
    missing = sorted(required - headers)
    if missing:
        raise ValueError("Missing CSV columns: " + ", ".join(missing))

    allowed_actions = {"", "CONFIRM_MATCH", "REGISTER_REMITTER_NAME", "IGNORE"}
    prepared: list[dict[str, str]] = []
    seen: set[str] = set()
    errors: list[str] = []
    for row_no, row in enumerate(reader, 2):
        candidate_id = str(row.get("id") or "").strip()
        if not candidate_id:
            errors.append(f"row {row_no}: id is required")
            continue
        if candidate_id in seen:
            errors.append(f"row {row_no}: duplicate candidate id {candidate_id}")
            continue
        seen.add(candidate_id)
        candidate_row = db.execute(
            text(f"SELECT * FROM {CANDIDATE_TABLE} WHERE id=:id"),
            {"id": candidate_id},
        ).first()
        if not candidate_row:
            errors.append(f"row {row_no}: candidate not found: {candidate_id}")
            continue
        candidate = _row(candidate_row)
        batch_id = str(row.get("candidate_batch_id") or "").strip()
        bank_codes = str(row.get("bank_codes") or "").strip()
        if batch_id != str(candidate.get("candidate_batch_id") or ""):
            errors.append(f"row {row_no}: candidate_batch_id does not match")
        if bank_codes != str(candidate.get("bank_codes") or ""):
            errors.append(f"row {row_no}: bank_codes does not match")
        action = str(row.get("resolution_action") or "").strip().upper()
        if action not in allowed_actions:
            errors.append(f"row {row_no}: unsupported resolution_action {action}")
        customer_value = str(row.get("matched_customer_id") or "").strip()
        customer_id = customer_name = ""
        if action in {"CONFIRM_MATCH", "REGISTER_REMITTER_NAME"}:
            if not customer_value:
                errors.append(f"row {row_no}: matched_customer_id is required for {action}")
            else:
                customer_row = db.execute(
                    text("SELECT id,customer_id,formal_name FROM tlc_customer_master "
                         "WHERE id=:value OR customer_id=:value LIMIT 1"),
                    {"value": customer_value},
                ).first()
                if not customer_row:
                    errors.append(f"row {row_no}: customer not found: {customer_value}")
                else:
                    customer = _row(customer_row)
                    customer_id = str(customer.get("customer_id") or "")
                    customer_name = str(customer.get("formal_name") or "")
        elif action == "IGNORE":
            customer_id = customer_name = ""
        elif customer_value:
            customer_row = db.execute(
                text("SELECT customer_id,formal_name FROM tlc_customer_master "
                     "WHERE id=:value OR customer_id=:value LIMIT 1"),
                {"value": customer_value},
            ).first()
            if not customer_row:
                errors.append(f"row {row_no}: customer not found: {customer_value}")
            else:
                customer = _row(customer_row)
                customer_id = str(customer.get("customer_id") or "")
                customer_name = str(customer.get("formal_name") or "")
        prepared.append({
            "id": candidate_id,
            "action": action,
            "customer": customer_id,
            "customer_name": customer_name,
            "comment": str(row.get("review_comment") or "").strip(),
        })

    if errors:
        raise ValueError("CSV validation failed: " + " | ".join(errors[:20]))
    if not prepared:
        raise ValueError("CSV contains no candidate rows")

    stamp = now()
    try:
        for item in prepared:
            db.execute(text(f"""UPDATE {CANDIDATE_TABLE}
              SET matched_customer_id=:customer,matched_customer_name=:customer_name,
                  resolution_action=:action,review_comment=:comment,reviewer=:reviewer,
                  updated_at=:stamp WHERE id=:id"""), {
                **item, "reviewer": reviewer, "stamp": stamp,
            })
            db.execute(text(f"""INSERT INTO {AUDIT_TABLE}
              (candidate_id,actor,action,detail,created_at)
              VALUES(:id,:actor,'IMPORT_REVIEW_CSV',:detail,:stamp)"""), {
                "id": item["id"], "actor": reviewer,
                "detail": f"action={item['action']}; customer_id={item['customer']}",
                "stamp": stamp,
            })
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"updated": len(prepared), "errors": []}


def resolve_candidate(db: Session, candidate_id: str, action: str, reviewer: str, customer_id: str = "", comment: str = "") -> dict[str, Any]:
    ensure_schema(db)
    candidate_row = db.execute(text(f"SELECT * FROM {CANDIDATE_TABLE} WHERE id=:id"), {"id": candidate_id}).first()
    if not candidate_row:
        raise LookupError("Bank remitter candidate was not found")
    candidate = _row(candidate_row)
    action = str(action or "").strip().upper()
    reviewer = str(reviewer or "").strip()
    if not reviewer:
        raise ValueError("reviewer is required")
    target_code = str(customer_id or candidate.get("matched_customer_id") or "").strip()
    name_identity_field = "NAME_IDENTITY"
    if action in {"CONFIRM_MATCH", "REGISTER_REMITTER_NAME"}:
        customer_row = db.execute(text("SELECT * FROM tlc_customer_master WHERE id=:value OR customer_id=:value LIMIT 1"), {"value": target_code}).first()
        if not customer_row:
            raise ValueError("Customer was not found")
        customer = _row(customer_row)
        target_code = str(customer["customer_id"])
        if action == "REGISTER_REMITTER_NAME":
            remitter = str(candidate["raw_remitter_name"])
            register_name(db, customer_record_id=str(customer["id"]), customer_id=target_code,
                          name_value=remitter, name_type="BANK_REMITTER",
                          source_system="BANK_REMITTER_CANDIDATE", actor=reviewer)
    elif action != "IGNORE":
        raise ValueError("Unsupported resolution action")
    status = "IGNORED" if action == "IGNORE" else "RESOLVED"
    stamp = now()
    db.execute(text(f"""UPDATE {CANDIDATE_TABLE} SET review_status=:status,resolution_action=:action,
      matched_customer_id=:customer,name_identity_field=:name_identity_field,reviewer=:reviewer,review_comment=:comment,
      reviewed_at=:stamp,updated_at=:stamp WHERE id=:id"""), {
        "status": status, "action": action, "customer": target_code if action != "IGNORE" else "",
        "name_identity_field": name_identity_field, "reviewer": reviewer, "comment": str(comment or ""), "stamp": stamp, "id": candidate_id,
    })
    db.execute(text(f"INSERT INTO {AUDIT_TABLE}(candidate_id,actor,action,detail,created_at) VALUES(:id,:actor,:action,:detail,:stamp)"), {
        "id": candidate_id, "actor": reviewer, "action": action,
        "detail": f"customer_id={target_code}; name_identity_field={name_identity_field}", "stamp": stamp,
    })
    db.commit()
    return _row(db.execute(text(f"SELECT * FROM {CANDIDATE_TABLE} WHERE id=:id"), {"id": candidate_id}).first())
