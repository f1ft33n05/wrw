
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException, Depends
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from database_models import User, Contact
from pydantic import BaseModel
from database import get_db, db_dependency
from starlette import status
from typing import Annotated
from models import CreateContactRequest
from models import Role
from routes.auth import RoleChecker


router = APIRouter(
    prefix="/contacts",
    tags=["contacts"]
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

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

@router.get(
    "/",
    response_model=list[CreateContactRequest],
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))],
)
async def list_contacts(db: db_dependency):
    contacts = db.query(Contact).all()
    return [
        CreateContactRequest(
            id=contact.id,
            name=contact.name,
            email=contact.email,
            phone=contact.phone,
            address=contact.address,
            outstanding_balance=contact.outstanding_balance,
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
        outstanding_balance = create_contact_request.outstanding_balance,
        contact_type = create_contact_request.contact_type,
        created_at = datetime.now(timezone.utc),
        updated_at = datetime.now(timezone.utc)
    )

    db.add(create_contact_model)
    db.commit()

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
        outstanding_balance=contact.outstanding_balance,
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

    contact.name = update_contact_request.name
    contact.email = update_contact_request.email
    contact.phone = update_contact_request.phone
    contact.address = update_contact_request.address
    contact.outstanding_balance = update_contact_request.outstanding_balance
    contact.contact_type = update_contact_request.contact_type
    contact.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(contact)

    return CreateContactRequest(
        id=contact.id,
        name=contact.name,
        email=contact.email,
        phone=contact.phone,
        address=contact.address,
        outstanding_balance=contact.outstanding_balance,
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

    db.delete(contact)
    db.commit()