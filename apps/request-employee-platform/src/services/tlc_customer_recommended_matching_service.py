from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_sales_ledger_evidence_service import list_sales_evidence
from src.services.tlc_bank_payment_evidence_service import list_bank_payment_evidence
from src.services.tlc_customer_reconciliation_case_service import ensure_tables as ensure_case_tables

TABLE = "tlc_customer_recommended_match"
AUDIT = "tlc_customer_recommended_match_audit"
ALLOWED = {"RECOMMENDED", "ACCEPTED", "REJECTED", "CANCELLED"}


def ensure_tables(db: Session) -> None:
    ensure_case_tables(db)
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {TABLE}(
      id VARCHAR(64) PRIMARY KEY,reconciliation_id VARCHAR(64) NOT NULL,snapshot_id VARCHAR(64) NOT NULL,
      customer_id VARCHAR(255) NOT NULL,customer_name VARCHAR(500) NOT NULL DEFAULT '',
      sales_record_id VARCHAR(255) NOT NULL DEFAULT '',payment_record_id VARCHAR(255) NOT NULL DEFAULT '',
      sales_document_no VARCHAR(255) NOT NULL DEFAULT '',payment_reference_no VARCHAR(255) NOT NULL DEFAULT '',
      sales_date VARCHAR(32) NOT NULL DEFAULT '',payment_date VARCHAR(32) NOT NULL DEFAULT '',
      sales_amount VARCHAR(64) NOT NULL DEFAULT '0',payment_amount VARCHAR(64) NOT NULL DEFAULT '0',
      difference_amount VARCHAR(64) NOT NULL DEFAULT '0',amount_score INTEGER NOT NULL DEFAULT 0,
      date_score INTEGER NOT NULL DEFAULT 0,total_score INTEGER NOT NULL DEFAULT 0,
      recommendation_rule VARCHAR(255) NOT NULL,status VARCHAR(64) NOT NULL DEFAULT 'RECOMMENDED',
      created_by VARCHAR(255) NOT NULL,created_at VARCHAR(64) NOT NULL,decided_by VARCHAR(255) NOT NULL DEFAULT '',
      decided_at VARCHAR(64) NOT NULL DEFAULT '',note TEXT NOT NULL DEFAULT '',
      UNIQUE(reconciliation_id,sales_record_id,payment_record_id))"""))
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {AUDIT}(
      id VARCHAR(64) PRIMARY KEY,recommendation_id VARCHAR(64) NOT NULL,reconciliation_id VARCHAR(64) NOT NULL,
      event_type VARCHAR(128) NOT NULL,actor VARCHAR(255) NOT NULL,event_at VARCHAR(64) NOT NULL,
      old_status VARCHAR(64) NOT NULL DEFAULT '',new_status VARCHAR(64) NOT NULL DEFAULT '',message TEXT NOT NULL DEFAULT '')"""))
    db.commit()


def _row(r: Any) -> dict[str, Any]: return dict(r._mapping)
def _dec(v: Any) -> Decimal:
    try: return Decimal(str(v or "0").replace(",", ""))
    except (InvalidOperation, ValueError): return Decimal("0")
def _fmt(v: Decimal) -> str:
    s = format(v.quantize(Decimal("0.01")), "f")
    return s.rstrip("0").rstrip(".") if "." in s else s

def _date_score(a: str, b: str) -> int:
    try: days = abs((date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days)
    except Exception: days = 9999
    return 100 if days == 0 else 95 if days <= 3 else 90 if days <= 7 else 80 if days <= 14 else 65 if days <= 31 else 45 if days <= 60 else 20

def _amount_score(sales: Decimal, payment: Decimal) -> tuple[int, Decimal]:
    diff = sales - payment
    absolute = abs(diff)
    if sales <= 0 or payment <= 0: return 0, diff
    ratio = absolute / max(abs(sales), abs(payment))
    if absolute == 0: return 100, diff
    if absolute <= Decimal("100"): return 95, diff
    if ratio <= Decimal("0.001"): return 92, diff
    if ratio <= Decimal("0.005"): return 88, diff
    if ratio <= Decimal("0.01"): return 82, diff
    if ratio <= Decimal("0.03"): return 72, diff
    if ratio <= Decimal("0.05"): return 62, diff
    return 0, diff

def _case(db: Session, rid: str) -> dict[str, Any]:
    ensure_case_tables(db)
    r = db.execute(text("SELECT * FROM tlc_customer_reconciliation_case WHERE id=:id"), {"id": rid}).first()
    if not r: raise LookupError("Reconciliation case not found")
    return _row(r)

def _rid(rec: dict[str, Any], prefix: str, index: int) -> str:
    return str(rec.get("id") or "").strip() or f"{prefix}-{index}"

def _audit(db: Session, recommendation_id: str, reconciliation_id: str, event: str, actor: str,
           old_status: str = "", new_status: str = "", message: str = "") -> None:
    db.execute(text(f"""INSERT INTO {AUDIT}(id,recommendation_id,reconciliation_id,event_type,actor,event_at,old_status,new_status,message)
      VALUES(:id,:mid,:rid,:event,:actor,:at,:old,:new,:msg)"""), {
      "id": uuid4().hex, "mid": recommendation_id, "rid": reconciliation_id, "event": event,
      "actor": actor, "at": datetime.now(timezone.utc).isoformat(), "old": old_status,
      "new": new_status, "msg": message})

def generate_recommendations(db: Session, *, reconciliation_id: str, operator: str, minimum_score: int = 70) -> dict[str, Any]:
    ensure_tables(db)
    reconciliation_id, operator = reconciliation_id.strip(), operator.strip()
    minimum_score = min(max(int(minimum_score), 1), 100)
    if not reconciliation_id: raise ValueError("reconciliation_id is required")
    if not operator: raise ValueError("operator is required")
    case = _case(db, reconciliation_id)
    if case["status"] == "CANCELLED": raise ValueError("Cancelled reconciliation cannot be recommended")
    sales = list_sales_evidence(db, customer_id=case["customer_id"], customer_name=case.get("customer_name", ""),
        previous_cutoff=case["previous_request_cutoff"], current_cutoff=case["current_request_cutoff"], limit=5000)
    payments = list_bank_payment_evidence(db, customer_id=case["customer_id"], customer_name=case.get("customer_name", ""),
        previous_cutoff=case["previous_bank_cutoff"], current_cutoff=case["current_bank_cutoff"], limit=5000)
    created = existing = 0
    results = []
    for si, s in enumerate(sales["records"]):
        sa = _dec(s.get("amount"))
        if sa <= 0: continue
        sid = _rid(s, "SALES", si)
        for pi, p in enumerate(payments["records"]):
            pa = _dec(p.get("amount"))
            if pa <= 0: continue
            pid = _rid(p, "PAYMENT", pi)
            amount_score, diff = _amount_score(sa, pa)
            if amount_score == 0: continue
            date_score = _date_score(str(s.get("business_date") or ""), str(p.get("business_date") or ""))
            total_score = round(amount_score * 0.8 + date_score * 0.2)
            if total_score < minimum_score: continue
            found = db.execute(text(f"SELECT * FROM {TABLE} WHERE reconciliation_id=:rid AND sales_record_id=:sid AND payment_record_id=:pid"),
                {"rid": reconciliation_id, "sid": sid, "pid": pid}).first()
            if found:
                existing += 1; results.append(_row(found)); continue
            mid = uuid4().hex
            rule = "EXACT_AMOUNT_DATE" if diff == 0 and date_score >= 90 else "NEAR_AMOUNT_DATE"
            db.execute(text(f"""INSERT INTO {TABLE}(id,reconciliation_id,snapshot_id,customer_id,customer_name,
              sales_record_id,payment_record_id,sales_document_no,payment_reference_no,sales_date,payment_date,
              sales_amount,payment_amount,difference_amount,amount_score,date_score,total_score,recommendation_rule,status,created_by,created_at)
              VALUES(:id,:rid,:snap,:cid,:cname,:sid,:pid,:sdoc,:pref,:sdate,:pdate,:sa,:pa,:diff,:ascore,:dscore,:total,:rule,'RECOMMENDED',:op,:at)"""), {
              "id": mid, "rid": reconciliation_id, "snap": case["snapshot_id"], "cid": case["customer_id"],
              "cname": case.get("customer_name", ""), "sid": sid, "pid": pid,
              "sdoc": str(s.get("document_no") or s.get("id") or ""),
              "pref": str(p.get("reference_no") or p.get("id") or ""),
              "sdate": str(s.get("business_date") or ""), "pdate": str(p.get("business_date") or ""),
              "sa": _fmt(sa), "pa": _fmt(pa), "diff": _fmt(diff), "ascore": amount_score,
              "dscore": date_score, "total": total_score, "rule": rule, "op": operator,
              "at": datetime.now(timezone.utc).isoformat()})
            _audit(db, mid, reconciliation_id, "RECOMMENDATION_CREATED", operator,
                   new_status="RECOMMENDED", message=f"{rule} / score={total_score}")
            db.commit()
            results.append(_row(db.execute(text(f"SELECT * FROM {TABLE} WHERE id=:id"), {"id": mid}).first()))
            created += 1
    results.sort(key=lambda x: (-int(x["total_score"]), x["sales_date"]))
    return {"reconciliation_id": reconciliation_id, "sales_record_count": sales["record_count"],
      "payment_record_count": payments["record_count"], "created_count": created, "existing_count": existing,
      "recommendation_count": len(results), "minimum_score": minimum_score, "recommendations": results}

def decide_recommendation(db: Session, *, recommendation_id: str, status: str, operator: str, note: str = "") -> dict[str, Any]:
    ensure_tables(db)
    cur = db.execute(text(f"SELECT * FROM {TABLE} WHERE id=:id"), {"id": recommendation_id}).first()
    if not cur: raise LookupError("Recommended match not found")
    rec = _row(cur); operator, status = operator.strip(), status.strip().upper()
    if not operator: raise ValueError("operator is required")
    if status not in {"ACCEPTED", "REJECTED", "CANCELLED"}: raise ValueError("status must be ACCEPTED, REJECTED or CANCELLED")
    if rec["status"] not in {"RECOMMENDED", "ACCEPTED"}: raise ValueError("Only RECOMMENDED or ACCEPTED item can be updated")
    now = datetime.now(timezone.utc).isoformat()
    db.execute(text(f"UPDATE {TABLE} SET status=:status,decided_by=:op,decided_at=:at,note=:note WHERE id=:id"),
      {"status": status, "op": operator, "at": now, "note": note, "id": recommendation_id})
    _audit(db, recommendation_id, rec["reconciliation_id"], "RECOMMENDATION_DECIDED", operator,
           old_status=rec["status"], new_status=status, message=note)
    db.commit()
    return _row(db.execute(text(f"SELECT * FROM {TABLE} WHERE id=:id"), {"id": recommendation_id}).first())

def list_recommendations(db: Session, *, reconciliation_id: str = "", status: str = "", limit: int = 1000) -> list[dict[str, Any]]:
    ensure_tables(db); clauses=[]; params={"limit": min(max(int(limit),1),2000)}
    if reconciliation_id: clauses.append("reconciliation_id=:rid"); params["rid"]=reconciliation_id
    if status:
        status=status.strip().upper()
        if status not in ALLOWED: raise ValueError("Unsupported recommendation status")
        clauses.append("status=:status"); params["status"]=status
    where=f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return [_row(r) for r in db.execute(text(f"SELECT * FROM {TABLE} {where} ORDER BY total_score DESC,created_at DESC LIMIT :limit"),params).all()]

def list_recommendation_audit(db: Session, *, recommendation_id: str, limit: int = 1000) -> list[dict[str, Any]]:
    ensure_tables(db)
    return [_row(r) for r in db.execute(text(f"SELECT * FROM {AUDIT} WHERE recommendation_id=:id ORDER BY event_at DESC LIMIT :limit"),
      {"id": recommendation_id, "limit": min(max(int(limit),1),2000)}).all()]
