
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException, Depends
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from database_models import StockMvt, User, Contact, SalesTxn
from pydantic import BaseModel
from database import get_db, db_dependency
from starlette import status
from typing import Annotated
from models import CreateContactRequest, CreateSaleRequest
from contacts import update_contact
from items import update_item


router = APIRouter(
    prefix="/sales",
    tags=["sales"]
)

APP_TIMEZONE = ZoneInfo("Africa/Harare")

def serialize_timestamp(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(APP_TIMEZONE).isoformat()

@router.get("/", response_model=list[CreateSaleRequest])
async def list_sales(db: db_dependency):
    sales = db.query(SalesTxn).all()
    return [
        CreateSaleRequest(
            id=sale.id,
            customer_id=sale.customer_id,
            invoice_id=sale.invoice_id,
            item_id=sale.item_id,
            quantity=sale.quantity,
            total_price=sale.total_price,
            payment_method=sale.payment_method,
            added_by=sale.added_by,
            location=sale.location,
            created_at=serialize_timestamp(sale.created_at),
            updated_at=serialize_timestamp(sale.updated_at)
        )
        for sale in sales
    ]

@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_sale(db: db_dependency, create_sale_request: CreateSaleRequest):
    create_sale_model = SalesTxn(
        customer_id = create_sale_request.customer_id,
        invoice_id = create_sale_request.invoice_id,
        item_id = create_sale_request.item_id,
        quantity = create_sale_request.quantity,
        total_price = create_sale_request.total_price,
        payment_method = create_sale_request.payment_method,
        added_by = create_sale_request.added_by,
        location = create_sale_request.location, # if not provided, default to "store", if Event, specify "Event: (name of event)"
        created_at = datetime.now(timezone.utc),
        updated_at = datetime.now(timezone.utc)
    )
    db.add(create_sale_model)
    db.commit()
    db.refresh(create_sale_model)
    return {"message": "Sale created successfully", "sale_id": create_sale_model.id}

@router.post("/pay", status_code=status.HTTP_200_OK) # must work for both direct sales and invoiced sales
async def pay_sale(db: db_dependency, invoice_id: int, payment_method: str, tendered_amount: float):
    sale = db.query(SalesTxn).filter(SalesTxn.invoice_id == invoice_id).first()

    invoice_amount = sale.total_price

    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")

    change_due = tendered_amount - invoice_amount


    if change_due < 0:
        outstanding_balance = -(float(invoice_amount) - tendered_amount)

    update_item()

    sale.payment_method = payment_method
    sale.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Sale payment updated successfully", "sale_id": sale.id, "change_due": change_due, "outstanding_balance": outstanding_balance}