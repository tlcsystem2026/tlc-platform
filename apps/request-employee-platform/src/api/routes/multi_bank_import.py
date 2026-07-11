from fastapi import APIRouter, Depends, HTTPException, Request
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
    db: Session = Depends(get_db),
):
    content = await request.body()
    try:
        bank_code = detect_bank_csv(content)
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
