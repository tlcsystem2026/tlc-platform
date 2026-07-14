
from fastapi import APIRouter, HTTPException
from src.services.bank_folder_settings_service import (
    check_bank_folder_settings,
    ensure_bank_account_directories,
    get_bank_folder_settings,
    save_bank_folder_settings,
)
router = APIRouter(prefix="/api/tlc-system-parameters/bank-folders", tags=["tlc-system-parameters"])

@router.get("")
def get_settings():
    return get_bank_folder_settings()

@router.put("")
def save_settings(payload: dict):
    try:
        return save_bank_folder_settings(payload)
    except (ValueError, RuntimeError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/check")
def check_settings():
    try:
        return check_bank_folder_settings()
    except (RuntimeError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/bank-accounts/{bank_account_code}/ensure")
def ensure_bank_account(bank_account_code: str):
    try:
        return ensure_bank_account_directories(bank_account_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
