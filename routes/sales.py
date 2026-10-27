
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from database_models import SalesTxn
from database import db_dependency
from starlette import status
from models import CreateSaleRequest, Role
from routes.auth import RoleChecker, get_current_user


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

@router.get(
    "/",
    response_model=list[CreateSaleRequest],
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))],
)
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

@router.post(
    "/pos",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))],
)
async def create_sale(
    db: db_dependency,
    create_sale_request: CreateSaleRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    create_sale_model = SalesTxn(
        customer_id = create_sale_request.customer_id,
        invoice_id = create_sale_request.invoice_id,
        item_id = create_sale_request.item_id,
        quantity = create_sale_request.quantity,
        total_price = create_sale_request.total_price,
        payment_method = create_sale_request.payment_method,
        added_by = current_user["id"],
        location = create_sale_request.location, # if not provided, default to "store", if Event, specify "Event: (name of event)"
        created_at = datetime.now(timezone.utc),
        updated_at = datetime.now(timezone.utc)
    )
    db.add(create_sale_model)
    db.commit()
    db.refresh(create_sale_model)
    return {"message": "Sale created successfully", "sale_id": create_sale_model.id}

@router.post(
    "/pay",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))],
)
async def pay_sale(db: db_dependency, invoice_id: int, payment_method: str, tendered_amount: float):
    sale = db.query(SalesTxn).filter(SalesTxn.invoice_id == invoice_id).first()
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")

    invoice_amount = float(sale.total_price)
    change_due = tendered_amount - invoice_amount
    outstanding_balance = max(invoice_amount - tendered_amount, 0)

    sale.payment_method = payment_method
    sale.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Sale payment updated successfully", "sale_id": sale.id, "change_due": change_due, "outstanding_balance": outstanding_balance}