from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from src.db.session import SessionLocal
from src.services.tlc_database_maintenance_service import (
    clear_table,
    create_full_backup,
    create_table_backup,
    list_audit,
    list_backups,
    list_tables,
    restore_full_backup,
    restore_table_backup,
)


router = APIRouter(tags=["tlc-database-maintenance"])


def _engine():
    return SessionLocal.kw["bind"]


def _run(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/database-maintenance-center", response_class=HTMLResponse)
def page():
    return HTMLResponse((Path(__file__).parents[2] / "web/static/database_maintenance_center.html").read_text(encoding="utf-8"))


@router.get("/api/database-maintenance/overview")
def overview():
    engine = _engine()
    return {"tables": list_tables(engine), "backups": list_backups(), "audit": list_audit(engine)}


@router.post("/api/database-maintenance/full-backup")
def full_backup(payload: dict):
    return _run(create_full_backup, _engine(), payload.get("operator", ""), payload.get("role", ""), payload.get("reason", ""))


@router.post("/api/database-maintenance/full-restore")
def full_restore(payload: dict):
    return _run(restore_full_backup, _engine(), payload.get("backup_id", ""), payload.get("operator", ""), payload.get("role", ""), payload.get("reason", ""), payload.get("confirmation", ""))


@router.post("/api/database-maintenance/tables/{table_name}/backup")
def table_backup(table_name: str, payload: dict):
    return _run(create_table_backup, _engine(), table_name, payload.get("operator", ""), payload.get("role", ""), payload.get("reason", ""))


@router.post("/api/database-maintenance/tables/{table_name}/restore")
def table_restore(table_name: str, payload: dict):
    return _run(restore_table_backup, _engine(), table_name, payload.get("backup_id", ""), payload.get("operator", ""), payload.get("role", ""), payload.get("reason", ""), payload.get("confirmation", ""))


@router.post("/api/database-maintenance/tables/{table_name}/clear")
def table_clear(table_name: str, payload: dict):
    return _run(clear_table, _engine(), table_name, payload.get("operator", ""), payload.get("role", ""), payload.get("reason", ""), payload.get("confirmation", ""))
