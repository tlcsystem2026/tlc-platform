from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_legal_entity_master_service import (
    LegalEntityDeleteConflict,
    audit_rows,
    delete_entity,
    list_entities,
    reference_counts,
    save_entity,
    set_default,
)


router = APIRouter(tags=["tlc-legal-entity-master"])


@router.get("/legal-entity-master", response_class=HTMLResponse)
def page():
    path = Path(__file__).parents[2] / "web/static/legal_entity_master.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/api/legal-entities")
def entities(keyword: str = "", include_inactive: bool = True, db: Session = Depends(get_db)):
    return list_entities(db, keyword, include_inactive)


@router.post("/api/legal-entities")
def save(payload: dict, db: Session = Depends(get_db)):
    try:
        return save_entity(db, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, detail=str(exc)) from exc


@router.post("/api/legal-entities/{entity_id}/default")
def make_default(entity_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return set_default(db, entity_id, str(payload.get("operator") or ""))
    except LookupError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@router.get("/api/legal-entities/{entity_id}/references")
def references(entity_id: str, db: Session = Depends(get_db)):
    return {"id": entity_id, "references": reference_counts(db, entity_id)}


@router.delete("/api/legal-entities/{entity_id}")
def delete(entity_id: str, operator: str, role: str, db: Session = Depends(get_db)):
    try:
        return delete_entity(db, entity_id, operator, role)
    except LegalEntityDeleteConflict as exc:
        raise HTTPException(409, detail={"message": str(exc), "references": exc.references}) from exc
    except PermissionError as exc:
        raise HTTPException(403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@router.get("/api/legal-entities-audit")
def audit(limit: int = 100, db: Session = Depends(get_db)):
    return audit_rows(db, limit)
