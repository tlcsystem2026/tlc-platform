from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.request_document_compare_adapter import compare_request_documents, to_legacy_compare_payload
from src.services import request_excel_document_adapter as excel_adapter
from src.services import request_pdf_document_adapter as pdf_adapter
from src.services.tlc_batch_request_import_service import FILE_TABLE, ensure_tables
from src.services.tlc_batch_service import append_timeline, get_batch, transition_batch

COMPARE_TABLE="tlc_batch_compare_result"

def ensure_compare_table(db:Session)->None:
    ensure_tables(db)
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {COMPARE_TABLE}(
      id VARCHAR(64) PRIMARY KEY,
      batch_id VARCHAR(64) NOT NULL,
      excel_file_id VARCHAR(64) NOT NULL,
      pdf_file_id VARCHAR(64) NOT NULL,
      request_no VARCHAR(255) NOT NULL DEFAULT '',
      matched INTEGER NOT NULL DEFAULT 0,
      difference_count INTEGER NOT NULL DEFAULT 0,
      result_json TEXT NOT NULL DEFAULT '{{}}',
      status VARCHAR(64) NOT NULL,
      compared_by VARCHAR(255) NOT NULL,
      compared_at VARCHAR(64) NOT NULL,
      UNIQUE(batch_id,excel_file_id,pdf_file_id)
    )"""))
    db.commit()

def _row(row:Any)->dict[str,Any]:
    d=dict(row._mapping);d["matched"]=bool(d.get("matched",0))
    try:d["result"]=json.loads(d.pop("result_json") or "{}")
    except Exception:d["result"]={}
    return d

def _active(db:Session,batch_id:str,file_type:str)->dict[str,Any]:
    row=db.execute(text(f"""SELECT * FROM {FILE_TABLE}
      WHERE batch_id=:b AND file_type=:t AND active=1
      ORDER BY version_no DESC LIMIT 1"""),{"b":batch_id,"t":file_type}).first()
    if not row:raise ValueError(f"Active {file_type} file is required")
    return dict(row._mapping)

def _resolve_adapter(module: Any, candidates: tuple[str, ...]):
    for name in candidates:
        function = getattr(module, name, None)
        if callable(function):
            return function
    available = sorted(
        name for name in dir(module)
        if not name.startswith("_") and callable(getattr(module, name, None))
    )
    raise ValueError(
        "No compatible request document parser found. "
        f"Tried {candidates}; available callables={available}"
    )


def _invoke_parser(function: Any, content: bytes, source_name: str):
    attempts = (
        lambda: function(content, source_name=source_name),
        lambda: function(content, filename=source_name),
        lambda: function(content, source_file=source_name),
        lambda: function(content),
    )
    last_error: TypeError | None = None
    for attempt in attempts:
        try:
            return attempt()
        except TypeError as exc:
            last_error = exc
    raise last_error or TypeError("Unable to invoke request document parser")


def _parse_excel(content: bytes, name: str):
    function = _resolve_adapter(
        excel_adapter,
        (
            "parse_request_excel_document",
            "parse_excel_request_document",
            "parse_request_document_excel",
            "parse_request_document",
            "parse_excel_document",
        ),
    )
    return _invoke_parser(function, content, name)


def _parse_pdf(content: bytes, name: str):
    function = _resolve_adapter(
        pdf_adapter,
        (
            "parse_request_document_pdf",
            "parse_request_pdf_document",
            "parse_pdf_request_document",
            "parse_request_document",
            "parse_pdf_document",
        ),
    )
    return _invoke_parser(function, content, name)

def _payload(result:Any)->dict[str,Any]:
    try:
        p=to_legacy_compare_payload(result)
        if isinstance(p,dict):return p
    except Exception:pass
    if hasattr(result,"as_dict"):
        p=result.as_dict()
        if isinstance(p,dict):return p
    if hasattr(result,"__dict__"):
        p=dict(result.__dict__)
        p["differences"]=[x.__dict__ if hasattr(x,"__dict__") else x for x in p.get("differences",[])]
        return p
    raise ValueError("Unsupported compare result contract")

def run_batch_compare(db:Session,*,batch_id:str,compared_by:str)->dict[str,Any]:
    ensure_compare_table(db)
    batch=get_batch(db,batch_id)
    if not batch:raise LookupError("Batch not found")
    if batch["status"]=="FINISHED":raise ValueError("Finished batch cannot be compared")
    compared_by=str(compared_by or "").strip()
    if not compared_by:raise ValueError("compared_by is required")
    excel=_active(db,batch_id,"REQUEST_EXCEL");pdf=_active(db,batch_id,"REQUEST_PDF")
    existing=db.execute(text(f"""SELECT * FROM {COMPARE_TABLE}
      WHERE batch_id=:b AND excel_file_id=:e AND pdf_file_id=:p"""),
      {"b":batch_id,"e":excel["id"],"p":pdf["id"]}).first()
    if existing:return {"status":"exists","compare_result":_row(existing)}
    ep=Path(excel["storage_path"]);pp=Path(pdf["storage_path"])
    if not ep.exists() or not pp.exists():raise ValueError("Stored request file is missing")
    result=compare_request_documents(_parse_excel(ep.read_bytes(),excel["original_name"]),_parse_pdf(pp.read_bytes(),pdf["original_name"]))
    payload=_payload(result)
    matched=bool(payload.get("matched",getattr(result,"matched",False)))
    diffs=payload.get("differences",[])
    count=int(payload.get("difference_count",len(diffs)))
    request_no=str(payload.get("request_no",getattr(result,"request_no","")) or "")
    rid=uuid4().hex;now=datetime.now(timezone.utc).isoformat()
    db.execute(text(f"""INSERT INTO {COMPARE_TABLE}(
      id,batch_id,excel_file_id,pdf_file_id,request_no,matched,difference_count,
      result_json,status,compared_by,compared_at
    ) VALUES(:id,:b,:e,:p,:r,:m,:c,:j,:s,:u,:t)"""),
    {"id":rid,"b":batch_id,"e":excel["id"],"p":pdf["id"],"r":request_no,
     "m":1 if matched else 0,"c":count,"j":json.dumps(payload,ensure_ascii=False,default=str),
     "s":"MATCHED" if matched else "ERROR","u":compared_by,"t":now})
    append_timeline(db,batch_id=batch_id,event_type="REQUEST_COMPARE_COMPLETED",
      old_status=batch["status"],new_status=batch["status"],
      message=("Matched" if matched else f"Differences={count}"),operator=compared_by)
    db.commit()
    current=get_batch(db,batch_id)
    if current["status"]=="IMPORTING":
        transition_batch(db,batch_id,new_status="COMPARE",operator=compared_by,message="Comparison started")
        current=get_batch(db,batch_id)
    target="READY_REVIEW" if matched else "ERROR"
    if current["status"]!=target:
        transition_batch(db,batch_id,new_status=target,operator=compared_by,
          message="Ready for review" if matched else "Comparison differences found")
    row=db.execute(text(f"SELECT * FROM {COMPARE_TABLE} WHERE id=:id"),{"id":rid}).first()
    return {"status":"completed","compare_result":_row(row)}

def latest_batch_compare(db:Session,batch_id:str):
    ensure_compare_table(db)
    if not get_batch(db,batch_id):raise LookupError("Batch not found")
    row=db.execute(text(f"""SELECT * FROM {COMPARE_TABLE}
      WHERE batch_id=:b ORDER BY compared_at DESC LIMIT 1"""),{"b":batch_id}).first()
    return _row(row) if row else None

def list_batch_compares(db:Session,batch_id:str,limit:int=100):
    ensure_compare_table(db)
    if not get_batch(db,batch_id):raise LookupError("Batch not found")
    rows=db.execute(text(f"""SELECT * FROM {COMPARE_TABLE}
      WHERE batch_id=:b ORDER BY compared_at DESC LIMIT :l"""),
      {"b":batch_id,"l":min(max(int(limit),1),1000)}).all()
    return [_row(x) for x in rows]
