from pydantic import BaseModel
from enum import Enum
from decimal import Decimal
from typing import Literal
from pydantic import Field, field_validator

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
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    outstanding_balance: Decimal = Decimal("0")
    contact_type: Literal["customer", "supplier", "reseller"]
    created_at: str | None = None
    updated_at: str | None = None


class PurchaseLineRequest(BaseModel):
    item_id: int
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(gt=0)

    @field_validator("quantity", "unit_cost")
    @classmethod
    def values_must_be_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Purchase values must be finite")
        return value


class PurchaseCreateRequest(BaseModel):
    supplier_id: int
    items: list[PurchaseLineRequest] = Field(min_length=1)
    amount_paid: Decimal = Field(ge=0)
    payment_method: str | None = None

    @field_validator("amount_paid")
    @classmethod
    def amount_paid_must_be_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Payment amount must be finite")
        return value


class PurchasePaymentRequest(BaseModel):
    purchase_id: int
    amount: Decimal = Field(gt=0)
    payment_method: str = Field(min_length=1)

    @field_validator("amount")
    @classmethod
    def amount_must_be_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Payment amount must be finite")
        return value


class ResellerAllocationLineRequest(BaseModel):
    item_id: int
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(gt=0)

    @field_validator("quantity", "unit_price")
    @classmethod
    def values_must_be_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Allocation values must be finite")
        return value

    @field_validator("quantity", "unit_price")
    @classmethod
    def values_must_have_cents_precision(cls, value: Decimal) -> Decimal:
        if value.as_tuple().exponent < -2:
            raise ValueError("Allocation values may have at most two decimal places")
        return value


class ResellerAllocationRequest(BaseModel):
    reseller_id: int
    items: list[ResellerAllocationLineRequest] = Field(min_length=1)


class ResellerReconciliationLineRequest(BaseModel):
    allocation_line_id: int
    quantity_sold: Decimal = Field(ge=0)
    quantity_returned: Decimal = Field(ge=0)

    @field_validator("quantity_sold", "quantity_returned")
    @classmethod
    def quantities_must_be_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Reconciliation quantities must be finite")
        return value


class ResellerReconciliationRequest(BaseModel):
    reseller_id: int
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    lines: list[ResellerReconciliationLineRequest] = Field(default_factory=list)


class ResellerPaymentRequest(BaseModel):
    reseller_id: int
    amount: Decimal = Field(gt=0)
    payment_method: str = Field(min_length=1)

    @field_validator("amount")
    @classmethod
    def amount_must_be_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Payment amount must be finite")
        return value

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
    wholesale_threshold: Decimal = Field(default=Decimal("6"), gt=0)
    quantity: float
    unit: str
    created_at: str | None = None
    updated_at: str | None = None

    @field_validator("wholesale_threshold")
    @classmethod
    def wholesale_threshold_must_be_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Wholesale threshold must be finite")
        return value


class SaleLineRequest(BaseModel):
    item_id: int
    quantity: Decimal = Field(gt=0)

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Quantity must be finite")
        return value


class CheckoutRequest(BaseModel):
    customer_id: int | None = None
    location: str = "store"
    items: list[SaleLineRequest] = Field(min_length=1)
    amount_paid: Decimal = Field(ge=0)
    payment_method: str | None = None

    @field_validator("amount_paid")
    @classmethod
    def amount_paid_must_be_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Amount paid must be finite")
        return value


class PaymentCollectionRequest(BaseModel):
    invoice_id: int
    amount: Decimal = Field(gt=0)
    payment_method: str = Field(min_length=1)

    @field_validator("amount")
    @classmethod
    def amount_must_be_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Payment amount must be finite")
        return value


class SaleTransactionResponse(BaseModel):
    id: int
    invoice_id: int
    receipt_url: str
    customer_id: int | None = None
    invoice_status: str | None = None
    invoice_total: Decimal | None = None
    amount_paid: Decimal = Decimal("0")
    balance_due: Decimal | None = None
    item_id: int
    item_name: str | None = None
    quantity: Decimal
    unit_price: Decimal | None = None
    total_price: Decimal
    price_type: str | None = None
    payment_method: str | None = None
    added_by: int | None = None
    location: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SalePaymentResponse(BaseModel):
    id: int
    invoice_id: int
    amount: Decimal
    payment_method: str
    status: str
    collected_by: int | None = None
    created_at: str | None = None
