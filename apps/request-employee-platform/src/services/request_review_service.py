
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session

ALLOWED={"WAIT_REVIEW","REVIEWED_OK","SOURCE_CORRECTION_REQUIRED","ON_HOLD"}

def ensure_review_tables(db:Session)->None:
    db.execute(text("""
    CREATE TABLE IF NOT EXISTS tlc_request_review_audit(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      review_id VARCHAR(64) NOT NULL,
      old_status VARCHAR(64) NOT NULL,
      new_status VARCHAR(64) NOT NULL,
      operator VARCHAR(255) NOT NULL,
      comment TEXT NOT NULL DEFAULT '',
      forced INTEGER NOT NULL DEFAULT 0,
      created_at VARCHAR(64) NOT NULL
    )"""))
    cols={r[1] for r in db.execute(text("PRAGMA table_info(tlc_request_review_queue)")).all()}
    if "reviewer" not in cols:
        db.execute(text("ALTER TABLE tlc_request_review_queue ADD COLUMN reviewer VARCHAR(255) NOT NULL DEFAULT ''"))
    if "reviewed_at" not in cols:
        db.execute(text("ALTER TABLE tlc_request_review_queue ADD COLUMN reviewed_at VARCHAR(64) NOT NULL DEFAULT ''"))
    if "review_comment" not in cols:
        db.execute(text("ALTER TABLE tlc_request_review_queue ADD COLUMN review_comment TEXT NOT NULL DEFAULT ''"))
    if "forced_review" not in cols:
        db.execute(text("ALTER TABLE tlc_request_review_queue ADD COLUMN forced_review INTEGER NOT NULL DEFAULT 0"))
    db.commit()

def _row(r)->dict[str,Any]:
    return dict(r._mapping)

def list_reviews(db:Session, business_month:str="", batch_id:str="", review_status:str="WAIT_REVIEW", compare_status:str="", customer_match_status:str="", keyword:str="", limit:int=500):
    ensure_review_tables(db)
    clauses=[]; params={"limit":min(max(int(limit),1),2000)}
    if business_month:
        clauses.append("q.business_month=:business_month"); params["business_month"]=business_month
    if batch_id:
        clauses.append("q.batch_id=:batch_id"); params["batch_id"]=batch_id
    if review_status:
        clauses.append("q.review_status=:review_status"); params["review_status"]=review_status
    if compare_status:
        clauses.append("q.compare_status=:compare_status"); params["compare_status"]=compare_status
    if customer_match_status:
        clauses.append("i.customer_match_status=:customer_match_status"); params["customer_match_status"]=customer_match_status
    if keyword:
        clauses.append("(q.pair_key LIKE :keyword OR q.raw_customer_name LIKE :keyword OR q.system_customer_name LIKE :keyword)")
        params["keyword"]=f"%{keyword}%"
    where=("WHERE "+" AND ".join(clauses)) if clauses else ""
    rows=db.execute(text(f"""
      SELECT q.*,i.pdf_file_name,i.excel_file_name,i.pdf_total_amount,i.excel_total_amount,
             i.exception_details,i.customer_match_status,i.final_pdf_path,i.final_excel_path,
             i.pdf_sha256,i.excel_sha256,i.pdf_raw_text,i.excel_raw_json,i.created_at AS imported_at
      FROM tlc_request_review_queue q
      JOIN tlc_request_batch_compare_item i ON i.id=q.item_id
      {where}
      ORDER BY q.created_at DESC LIMIT :limit
    """),params).all()
    return [_row(r) for r in rows]

def get_review(db:Session, review_id:str):
    ensure_review_tables(db)
    row=db.execute(text("""
      SELECT q.*,i.pdf_file_name,i.excel_file_name,i.pdf_total_amount,i.excel_total_amount,
             i.exception_details,i.customer_match_status,i.final_pdf_path,i.final_excel_path,
             i.pdf_sha256,i.excel_sha256,i.pdf_raw_text,i.excel_raw_json,i.created_at AS imported_at
      FROM tlc_request_review_queue q
      JOIN tlc_request_batch_compare_item i ON i.id=q.item_id
      WHERE q.id=:id
    """),{"id":review_id}).first()
    if not row: raise LookupError("Review item not found")
    return _row(row)

def update_review(db:Session, review_id:str, new_status:str, operator:str, comment:str="", forced:bool=False):
    ensure_review_tables(db)
    new_status=str(new_status or "").strip().upper()
    operator=str(operator or "").strip()
    comment=str(comment or "").strip()
    if new_status not in ALLOWED-{"WAIT_REVIEW"}: raise ValueError("Unsupported review status")
    if not operator: raise ValueError("operator is required")
    current=get_review(db,review_id)
    if current["review_status"]!="WAIT_REVIEW": raise ValueError("Only WAIT_REVIEW item can be updated")
    if new_status in {"SOURCE_CORRECTION_REQUIRED","ON_HOLD"} and not comment:
        raise ValueError("comment is required")
    if new_status=="REVIEWED_OK":
        clean=current["compare_status"]=="MATCHED" and current["customer_match_status"]=="MATCHED"
        if not clean and not forced:
            raise ValueError("Unresolved exception requires forced=true and a comment")
        if forced and not comment:
            raise ValueError("Forced review requires a comment")
    now=datetime.now(timezone.utc).isoformat()
    db.execute(text("""
      UPDATE tlc_request_review_queue
      SET review_status=:status,reviewer=:operator,reviewed_at=:now,
          review_comment=:comment,forced_review=:forced
      WHERE id=:id
    """),{"status":new_status,"operator":operator,"now":now,"comment":comment,"forced":1 if forced else 0,"id":review_id})
    db.execute(text("""
      INSERT INTO tlc_request_review_audit(review_id,old_status,new_status,operator,comment,forced,created_at)
      VALUES(:id,:old,:new,:operator,:comment,:forced,:now)
    """),{"id":review_id,"old":current["review_status"],"new":new_status,"operator":operator,"comment":comment,"forced":1 if forced else 0,"now":now})
    db.commit()
    return get_review(db,review_id)

def wait_review_count(db:Session)->int:
    ensure_review_tables(db)
    row=db.execute(text("SELECT COUNT(*) AS c FROM tlc_request_review_queue WHERE review_status='WAIT_REVIEW'")).first()
    return int(row._mapping["c"])

def cleanup_obvious_test_reviews(db:Session)->dict[str,int]:
    ensure_review_tables(db)
    rows=db.execute(text(
        "SELECT q.id AS review_id,q.item_id,q.batch_id "
        "FROM tlc_request_review_queue q "
        "WHERE q.pair_key='abc' "
        "OR (q.raw_customer_name='株式会社ABC' "
        "AND q.exception_codes LIKE '%TOTAL_AMOUNT_MISMATCH%') "
        "OR (q.system_customer_name='株式会社ABC' "
        "AND q.exception_codes LIKE '%TOTAL_AMOUNT_MISMATCH%')"
    )).all()

    review_ids=[r._mapping["review_id"] for r in rows]
    item_ids=[r._mapping["item_id"] for r in rows]
    batch_ids=list({r._mapping["batch_id"] for r in rows})

    for review_id in review_ids:
        db.execute(
            text("DELETE FROM tlc_request_review_audit WHERE review_id=:id"),
            {"id":review_id},
        )
        db.execute(
            text("DELETE FROM tlc_request_review_queue WHERE id=:id"),
            {"id":review_id},
        )

    for item_id in item_ids:
        db.execute(
            text("DELETE FROM tlc_request_batch_compare_item WHERE id=:id"),
            {"id":item_id},
        )

    deleted_batches=0
    for batch_id in batch_ids:
        remaining=db.execute(
            text(
                "SELECT COUNT(*) "
                "FROM tlc_request_batch_compare_item "
                "WHERE batch_id=:batch_id"
            ),
            {"batch_id":batch_id},
        ).scalar_one()
        if int(remaining or 0)==0:
            db.execute(
                text("DELETE FROM tlc_request_batch_compare WHERE id=:id"),
                {"id":batch_id},
            )
            deleted_batches+=1

    db.commit()
    return {
        "review_deleted":len(review_ids),
        "item_deleted":len(item_ids),
        "empty_batch_deleted":deleted_batches,
    }
