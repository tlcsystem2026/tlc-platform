from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from src.services.request_folder_settings_service import (
    check_request_folder_settings,
    ensure_month_directories,
    get_request_folder_settings,
    save_request_folder_settings,
)

router = APIRouter(prefix="/api/tlc-system-parameters/request-folders", tags=["tlc-system-parameters"])

@router.get("")
def get_settings():
    return get_request_folder_settings()

@router.put("")
def save_settings(payload: dict):
    try:
        return save_request_folder_settings(payload)
    except (ValueError, RuntimeError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/check")
def check_settings():
    try:
        return check_request_folder_settings()
    except (RuntimeError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/months/{business_month}/ensure")
def ensure_month(business_month: str):
    try:
        return ensure_month_directories(business_month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

page_router = APIRouter(tags=["tlc-system-parameter-center"])

@page_router.get("/system-parameter-center", response_class=HTMLResponse)
def page():
    page_path = Path(__file__).parents[2] / "web" / "static" / "system_parameter_center.html"
    return HTMLResponse(page_path.read_text(encoding="utf-8"))
