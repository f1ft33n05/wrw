from pydantic import BaseModel

class User(BaseModel):
    id: int
    username: str
    password: str
    role: str


class CreateUserRequest(BaseModel):
    id: int | None = None
    username: str
    password: str
    email: str
    phone: str
    role: str
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
    added_by: int
    location: str
    created_at: str | None = None
    updated_at: str | None = None
