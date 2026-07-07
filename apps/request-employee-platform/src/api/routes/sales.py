from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.db.models import SalesRecordORM
from src.repositories.legal_entity_repository import LegalEntityRepository
from src.services.export_service import export_xlsx, export_pdf

router = APIRouter(prefix="/api/sales", tags=["sales"])


class SalesPostRequest(BaseModel):
    legal_entity_id: str = "TEST-JP-01"
    request_no: str
    sales_date: str = ""
    customer_name: str = ""
    currency: str = "JPY"
    subtotal: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")


def _serialize(x):
    return {
        "id": x.id, "legal_entity_id": x.legal_entity_id, "request_no": x.request_no,
        "sales_date": str(x.sales_date or ""), "customer_name": x.customer_name,
        "currency": x.currency, "subtotal": str(x.subtotal), "tax_amount": str(x.tax_amount),
        "total_amount": str(x.total_amount), "status": x.status,
    }


def _search(db, keyword="", legal_entity_id="", status="", date_from="", date_to="",
            amount_min="", amount_max=""):
    q = db.query(SalesRecordORM)
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.filter(or_(SalesRecordORM.request_no.ilike(like),
                         SalesRecordORM.customer_name.ilike(like)))
    if legal_entity_id:
        q = q.filter(SalesRecordORM.legal_entity_id == legal_entity_id)
    if status:
        q = q.filter(SalesRecordORM.status == status)
    if date_from:
        q = q.filter(SalesRecordORM.sales_date >= date.fromisoformat(date_from))
    if date_to:
        q = q.filter(SalesRecordORM.sales_date <= date.fromisoformat(date_to))
    if amount_min:
        q = q.filter(SalesRecordORM.total_amount >= Decimal(amount_min))
    if amount_max:
        q = q.filter(SalesRecordORM.total_amount <= Decimal(amount_max))
    return q.order_by(SalesRecordORM.created_at.desc()).limit(500).all()


@router.get("")
def list_sales(keyword: str = "", legal_entity_id: str = "", status: str = "",
               date_from: str = "", date_to: str = "", amount_min: str = "",
               amount_max: str = "", db: Session = Depends(get_db)):
    return [_serialize(x) for x in _search(db, keyword, legal_entity_id, status, date_from, date_to, amount_min, amount_max)]


@router.get("/export/excel")
def export_sales_excel(keyword: str = "", legal_entity_id: str = "", status: str = "",
                       date_from: str = "", date_to: str = "", amount_min: str = "",
                       amount_max: str = "", db: Session = Depends(get_db)):
    rows = [_serialize(x) for x in _search(db, keyword, legal_entity_id, status, date_from, date_to, amount_min, amount_max)]
    return export_xlsx(rows, "sales_results")


@router.get("/export/pdf")
def export_sales_pdf(keyword: str = "", legal_entity_id: str = "", status: str = "",
                     date_from: str = "", date_to: str = "", amount_min: str = "",
                     amount_max: str = "", db: Session = Depends(get_db)):
    rows = [_serialize(x) for x in _search(db, keyword, legal_entity_id, status, date_from, date_to, amount_min, amount_max)]
    return export_pdf(rows, "sales_results", "Sales Search Results")


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    rows = db.query(SalesRecordORM).all()
    total = sum(Decimal(x.total_amount or 0) for x in rows)
    return {"count": len(rows), "total_amount": str(total), "currency": "JPY"}


@router.post("/post")
def post(req: SalesPostRequest, db: Session = Depends(get_db)):
    LegalEntityRepository(db).ensure(req.legal_entity_id)
    ex = db.query(SalesRecordORM).filter_by(
        legal_entity_id=req.legal_entity_id, request_no=req.request_no
    ).one_or_none()
    if ex:
        return {"status": "exists", "id": ex.id}
    obj = SalesRecordORM(
        id=uuid4().hex, legal_entity_id=req.legal_entity_id, request_no=req.request_no,
        sales_date=date.fromisoformat(req.sales_date) if req.sales_date else None,
        customer_name=req.customer_name, currency=req.currency, subtotal=req.subtotal,
        tax_amount=req.tax_amount, total_amount=req.total_amount, status="posted",
    )
    db.add(obj); db.commit()
    return {"status": "created", "id": obj.id}
