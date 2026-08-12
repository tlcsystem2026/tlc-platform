from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.multi_bank_csv_import_service import (
    detect_bank_csv,
    import_bank_transactions,
    parse_bank_csv,
)

router = APIRouter(prefix="/api/bank-import", tags=["bank-import"])


@router.post("/csv")
async def import_csv(
    request: Request,
    source_name: str = "bank.csv",
    selected_bank_code: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    content = await request.body()
    try:
        selected_bank_code = selected_bank_code.strip().upper()
        bank_code = detect_bank_csv(content)
        # TLC_BANK_IMPORT_SELECTED_BANK_VALIDATION_R1
        if bank_code != selected_bank_code:
            raise ValueError(
                "Selected bank does not match CSV format: "
                f"selected={selected_bank_code}, detected={bank_code}"
            )
        transactions = parse_bank_csv(content, source_file=source_name)
        result = import_bank_transactions(db, transactions)
        return {
            "bank_code": bank_code,
            "source_name": source_name,
            "parsed": len(transactions),
            **result,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
