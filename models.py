from pydantic import BaseModel
from enum import Enum

class Role(str, Enum):
    admin = "admin"
    manager = "manager"
    cashier = "cashier"


class User(BaseModel):
    id: int
    username: str
    password: str
    role: Role


class CreateUserRequest(BaseModel):
    id: int | None = None
    name: str
    username: str
    password: str
    email: str
    phone: str
    role: Role
    created_at: str | None = None
    updated_at: str | None = None


class UpdateUserRequest(BaseModel):
    name: str
    username: str
    email: str
    phone: str
    role: Role
    password: str | None = None


class UserResponse(BaseModel):
    id: int
    name: str
    username: str
    email: str
    phone: str
    role: Role
    created_at: str | None = None
    updated_at: str | None = None


class CreateContactRequest(BaseModel):
    id: int | None = None
    name: str
    email: str
    phone: str
    address: str
    outstanding_balance: float 
    contact_type: str
    created_at: str | None = None
    updated_at: str | None = None

class Token(BaseModel):
    access_token: str
    token_type: str

class CreateItemRequest(BaseModel):
    id: int | None = None
    name: str
    description: str
    barcode: str
    purchase_price: float
    selling_price_wholesale: float
    selling_price_retail: float
    quantity: float
    unit: str
    created_at: str | None = None
    updated_at: str | None = None

class CreateSaleRequest(BaseModel):
    id: int | None = None
    customer_id: int
    invoice_id: int
    item_id: int
    quantity: float
    total_price: float
    payment_method: str
    added_by: int | None = None
    location: str
    created_at: str | None = None
    updated_at: str | None = None
