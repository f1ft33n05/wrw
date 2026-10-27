
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from database_models import (
    Contact,
    Invoices,
    Payments,
    PurchaseTxns,
    Purchases,
    ResellerAllocations,
    ResellerPayments,
    ResellerReconciliations,
    ResellerTxns,
    SalesTxn,
    SupplierPayments,
)
from pydantic import BaseModel
from database import get_db, db_dependency
from starlette import status
from typing import Annotated
from models import CreateContactRequest
from models import Role
from routes.auth import RoleChecker, get_current_user
from routes.ledger_utils import decimal_value, format_money


router = APIRouter(prefix="/contacts", tags=["contacts"])
pages_router = APIRouter(tags=["contacts"])
templates = Jinja2Templates(directory="templates")
templates.env.filters["money"] = format_money

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

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

def contact_balance(db, contact: Contact) -> Decimal:
    if contact.contact_type == "supplier":
        purchases = (
            db.query(Purchases)
            .filter(Purchases.supplier_id == contact.id)
            .all()
        )
        total_due = Decimal("0")
        for purchase in purchases:
            paid = sum(
                (
                    decimal_value(payment.amount, "supplier payment")
                    for payment in db.query(SupplierPayments)
                    .filter(SupplierPayments.purchase_id == purchase.id)
                    .all()
                ),
                Decimal("0"),
            )
            total_due += max(
                decimal_value(purchase.total_amount, "purchase total") - paid,
                Decimal("0"),
            )
        return total_due
    if contact.contact_type == "reseller":
        reconciliations = (
            db.query(ResellerReconciliations)
            .filter(ResellerReconciliations.reseller_id == contact.id)
            .all()
        )
        payments = (
            db.query(ResellerPayments)
            .filter(ResellerPayments.reseller_id == contact.id)
            .all()
        )
        reconciled = sum(
            (
                decimal_value(row.total_due, "reconciliation total")
                for row in reconciliations
            ),
            Decimal("0"),
        )
        paid = sum(
            (decimal_value(row.amount, "reseller payment") for row in payments),
            Decimal("0"),
        )
        return max(reconciled - paid, Decimal("0"))
    invoices = (
        db.query(Invoices)
        .filter(Invoices.customer_id == contact.id)
        .all()
    )
    total_due = Decimal("0")
    for invoice in invoices:
        paid = sum(
            (
                decimal_value(payment.amount, "customer payment")
                for payment in db.query(Payments)
                .filter(
                    Payments.invoice_id == invoice.id,
                    Payments.status == "completed",
                )
                .all()
            ),
            Decimal("0"),
        )
        total_due += max(
            decimal_value(invoice.total_price, "invoice total") - paid,
            Decimal("0"),
        )
    return total_due


@pages_router.get(
    "/customers",
    response_class=HTMLResponse,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))],
)
@pages_router.get(
    "/suppliers",
    response_class=HTMLResponse,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))],
)
@pages_router.get(
    "/resellers",
    response_class=HTMLResponse,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))],
)
async def contact_category_page(
    request: Request,
    user: Annotated[dict, Depends(get_current_user)],
    db: db_dependency,
):
    contact_type = {
        "customers": "customer",
        "suppliers": "supplier",
        "resellers": "reseller",
    }[request.url.path.strip("/")]
    contacts = (
        db.query(Contact)
        .filter(Contact.contact_type == contact_type)
        .order_by(Contact.name)
        .all()
    )
    contact_balances = {
        contact.id: contact_balance(db, contact) for contact in contacts
    }
    return templates.TemplateResponse(
        request,
        "contacts.html",
        {
            "user": user,
            "contact_type": contact_type,
            "contacts": contacts,
            "contact_balances": contact_balances,
        },
    )

@router.get(
    "/",
    response_model=list[CreateContactRequest],
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))],
)
async def list_contacts(db: db_dependency, contact_type: str | None = None):
    query = db.query(Contact)
    if contact_type is not None:
        if contact_type not in {"customer", "supplier", "reseller"}:
            raise HTTPException(status_code=422, detail="Invalid contact type")
        query = query.filter(Contact.contact_type == contact_type)
    contacts = query.all()
    return [
        CreateContactRequest(
            id=contact.id,
            name=contact.name,
            email=contact.email,
            phone=contact.phone,
            address=contact.address,
            outstanding_balance=contact_balance(db, contact),
            contact_type=contact.contact_type,
            created_at=serialize_timestamp(contact.created_at),
            updated_at=serialize_timestamp(contact.updated_at)
        )
        for contact in contacts
    ]

@router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager))],
)
async def create_contact(db: db_dependency, create_contact_request: CreateContactRequest):
    create_contact_model = Contact(
        name = create_contact_request.name,
        email = create_contact_request.email,
        phone = create_contact_request.phone,
        address = create_contact_request.address,
        outstanding_balance = "0",
        contact_type = create_contact_request.contact_type,
        created_at = datetime.now(timezone.utc),
        updated_at = datetime.now(timezone.utc)
    )

    db.add(create_contact_model)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A contact with that email or phone already exists",
        ) from None
    db.refresh(create_contact_model)
    return CreateContactRequest(
        id=create_contact_model.id,
        name=create_contact_model.name,
        email=create_contact_model.email,
        phone=create_contact_model.phone,
        address=create_contact_model.address,
        outstanding_balance="0",
        contact_type=create_contact_model.contact_type,
        created_at=serialize_timestamp(create_contact_model.created_at),
        updated_at=serialize_timestamp(create_contact_model.updated_at),
    )

@router.get(
    "/{contact_id}",
    response_model=CreateContactRequest,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))],
)
async def get_contact(contact_id: int, db: db_dependency):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return CreateContactRequest(
        id=contact.id,
        name=contact.name,
        email=contact.email,
        phone=contact.phone,
        address=contact.address,
        outstanding_balance=contact_balance(db, contact),
        contact_type=contact.contact_type,
        created_at=serialize_timestamp(contact.created_at),
        updated_at=serialize_timestamp(contact.updated_at)
    )

@router.put(
    "/{contact_id}",
    response_model=CreateContactRequest,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager))],
)
async def update_contact(contact_id: int, update_contact_request: CreateContactRequest, db: db_dependency):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    if contact.contact_type != update_contact_request.contact_type:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact category cannot be changed; create a contact in the correct category",
        )

    contact.name = update_contact_request.name
    contact.email = update_contact_request.email
    contact.phone = update_contact_request.phone
    contact.address = update_contact_request.address
    contact.contact_type = update_contact_request.contact_type
    contact.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A contact with that email or phone already exists",
        ) from None
    db.refresh(contact)

    return CreateContactRequest(
        id=contact.id,
        name=contact.name,
        email=contact.email,
        phone=contact.phone,
        address=contact.address,
        outstanding_balance=contact_balance(db, contact),
        contact_type=contact.contact_type,
        created_at=serialize_timestamp(contact.created_at),
        updated_at=serialize_timestamp(contact.updated_at)
    )

@router.delete(
    "/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager))],
)
async def delete_contact(contact_id: int, db: db_dependency):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    if contact.contact_type == "customer":
        linked_records = (
            db.query(SalesTxn.id)
            .filter(SalesTxn.customer_id == contact_id)
            .first()
            or db.query(Invoices.id).filter(Invoices.customer_id == contact_id).first()
        )
    elif contact.contact_type == "supplier":
        linked_records = db.query(Purchases.id).filter(
            Purchases.supplier_id == contact_id
        ).first() or db.query(PurchaseTxns.id).filter(
            PurchaseTxns.supplier_id == contact_id
        ).first()
    else:
        linked_records = (
            db.query(ResellerAllocations.id)
            .filter(ResellerAllocations.reseller_id == contact_id)
            .first()
            or db.query(ResellerReconciliations.id)
            .filter(ResellerReconciliations.reseller_id == contact_id)
            .first()
            or db.query(ResellerPayments.id)
            .filter(ResellerPayments.reseller_id == contact_id)
            .first()
            or db.query(ResellerTxns.id)
            .filter(ResellerTxns.reseller_id == contact_id)
            .first()
        )
    if linked_records:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact has transaction history and cannot be deleted",
        )

    db.delete(contact)
    db.commit()