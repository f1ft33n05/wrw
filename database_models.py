from sqlalchemy import Column, Integer, String, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from config import CURRENCY_CODE

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    email = Column(String, unique=True, index=True)
    phone = Column(String, unique=True, index=True)
    role = Column(String)
    created_at = Column(String)
    updated_at = Column(String)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=False, default="")


class RoleDefinition(Base):
    __tablename__ = "role_definitions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(String)
    system_role = Column(Integer, default=0)
    created_at = Column(String)
    updated_at = Column(String)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String, nullable=False, index=True)
    module = Column(String, nullable=False, index=True)
    can_view = Column(Integer, default=0)
    can_create = Column(Integer, default=0)
    can_edit = Column(Integer, default=0)
    can_delete = Column(Integer, default=0)
    created_at = Column(String)
    updated_at = Column(String)

    __table_args__ = (UniqueConstraint("role_name", "module"),)

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    phone = Column(String, unique=True, index=True)
    outstanding_balance = Column(String)
    address = Column(String)
    contact_type = Column(String)  # e.g., "customer"
    created_at = Column(String)
    updated_at = Column(String)

class ItemCategory(Base):
    __tablename__ = "item_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String)
    created_at = Column(String)
    updated_at = Column(String)


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    barcode = Column(String, unique=True, index=True)
    purchase_price = Column(String)
    selling_price_wholesale = Column(String)
    selling_price_retail = Column(String)
    wholesale_threshold = Column(String, default="6")
    quantity = Column(String)
    unit = Column(String)
    category_id = Column(Integer)
    created_at = Column(String)
    updated_at = Column(String)


class ItemDiscount(Base):
    __tablename__ = "item_discounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    discount_type = Column(String, nullable=False)  # item or category
    target_id = Column(Integer, nullable=False)
    percentage = Column(String, nullable=False)
    active = Column(Integer, default=1)
    created_at = Column(String)
    updated_at = Column(String)

class SalesTxn(Base):
    __tablename__ = "sales_txns"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer)
    event_id = Column(Integer, index=True)
    invoice_id = Column(Integer)
    item_id = Column(Integer)
    quantity = Column(String)
    unit_price = Column(String)
    price_type = Column(String)
    total_price = Column(String)
    discount_percentage = Column(String)
    discount_amount = Column(String)
    payment_method = Column(String)
    added_by = Column(Integer)
    location = Column(String) # e.g., "store", "online", "Event: (name of event)"
    created_at = Column(String)
    updated_at = Column(String)

class PurchaseTxns(Base):
    __tablename__ = "purchase_txns"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer)
    item_id = Column(Integer)
    quantity = Column(String)
    total_price = Column(String)
    payment_method = Column(String)
    created_at = Column(String)
    updated_at = Column(String)

class ResellerTxns(Base):
    __tablename__ = "reseller_txns"

    id = Column(Integer, primary_key=True, index=True)
    reseller_id = Column(Integer)
    item_id = Column(Integer)
    quantity = Column(String)
    total_price = Column(String)
    payment_method = Column(String)
    created_at = Column(String)
    updated_at = Column(String)

class Purchases(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, nullable=False, index=True)
    total_amount = Column(String, nullable=False)
    created_by = Column(Integer)
    created_at = Column(String)
    updated_at = Column(String)

class PurchaseLines(Base):
    __tablename__ = "purchase_lines"

    id = Column(Integer, primary_key=True, index=True)
    purchase_id = Column(Integer, nullable=False, index=True)
    item_id = Column(Integer, nullable=False)
    quantity = Column(String, nullable=False)
    unit_cost = Column(String, nullable=False)
    total_amount = Column(String, nullable=False)

class SupplierPayments(Base):
    __tablename__ = "supplier_payments"

    id = Column(Integer, primary_key=True, index=True)
    purchase_id = Column(Integer, nullable=False, index=True)
    amount = Column(String, nullable=False)
    payment_method = Column(String, nullable=False)
    recorded_by = Column(Integer)
    created_at = Column(String)
    updated_at = Column(String)

class ResellerAllocations(Base):
    __tablename__ = "reseller_allocations"

    id = Column(Integer, primary_key=True, index=True)
    reseller_id = Column(Integer, nullable=False, index=True)
    allocated_by = Column(Integer)
    created_at = Column(String)
    updated_at = Column(String)

class ResellerAllocationLines(Base):
    __tablename__ = "reseller_allocation_lines"

    id = Column(Integer, primary_key=True, index=True)
    allocation_id = Column(Integer, nullable=False, index=True)
    item_id = Column(Integer, nullable=False)
    quantity_allocated = Column(String, nullable=False)
    quantity_remaining = Column(String, nullable=False)
    unit_price = Column(String, nullable=False)

class ResellerReconciliations(Base):
    __tablename__ = "reseller_reconciliations"

    id = Column(Integer, primary_key=True, index=True)
    reseller_id = Column(Integer, nullable=False, index=True)
    period = Column(String, nullable=False)
    reconciliation_date = Column(String)
    total_due = Column(String, nullable=False)
    reconciled_by = Column(Integer)
    created_at = Column(String)
    updated_at = Column(String)

class ResellerReconciliationLines(Base):
    __tablename__ = "reseller_reconciliation_lines"

    id = Column(Integer, primary_key=True, index=True)
    reconciliation_id = Column(Integer, nullable=False, index=True)
    allocation_line_id = Column(Integer, nullable=False)
    quantity_sold = Column(String, nullable=False)
    quantity_returned = Column(String, nullable=False)
    unit_price = Column(String, nullable=False)
    total_due = Column(String, nullable=False)

class ResellerPayments(Base):
    __tablename__ = "reseller_payments"

    id = Column(Integer, primary_key=True, index=True)
    reseller_id = Column(Integer, nullable=False, index=True)
    amount = Column(String, nullable=False)
    payment_method = Column(String, nullable=False)
    recorded_by = Column(Integer)
    created_at = Column(String)
    updated_at = Column(String)

class StockMvt(Base):
    __tablename__ = "stock_mvt"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer)
    quantity = Column(String)
    movement_type = Column(String)  # e.g., "in" or "out"
    note = Column(String)
    created_at = Column(String)
    updated_at = Column(String)

class Events(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    venue = Column(String)
    starts_at = Column(String)
    ends_at = Column(String)
    event_type = Column(String)
    description = Column(String)
    status = Column(String)
    created_at = Column(String)
    updated_at = Column(String)


class EventStockAllocation(Base):
    __tablename__ = "event_stock_allocations"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, nullable=False, index=True)
    item_id = Column(Integer, nullable=False, index=True)
    quantity = Column(String, nullable=False)
    quantity_remaining = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")
    allocated_by = Column(Integer)
    created_at = Column(String)
    updated_at = Column(String)

class Quotations(Base):
    __tablename__ = "quotations"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer)
    event_id = Column(Integer, index=True)
    document_number = Column(String, unique=True, index=True)
    issue_date = Column(String)
    expiry_date = Column(String)
    due_date = Column(String)
    notes = Column(String)
    subtotal = Column(String)
    tax_rate = Column(String)
    tax_amount = Column(String)
    discount_amount = Column(String)
    currency = Column(String, default=CURRENCY_CODE)
    created_by = Column(Integer)
    items = Column(String)  # JSON string of items, quantities and unit prices
    total_price = Column(String)
    status = Column(String)  # e.g., "pending", "approved", "rejected"
    created_at = Column(String)
    updated_at = Column(String)

class Invoices(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer)
    event_id = Column(Integer, index=True)
    document_number = Column(String, unique=True, index=True)
    issue_date = Column(String)
    due_date = Column(String)
    notes = Column(String)
    subtotal = Column(String)
    tax_rate = Column(String)
    tax_amount = Column(String)
    discount_amount = Column(String)
    currency = Column(String, default=CURRENCY_CODE)
    created_by = Column(Integer)
    items = Column(String)  # JSON string of items, quantities and unit prices
    total_price = Column(String)
    status = Column(String)  # e.g., "unpaid", "paid", "overdue"
    created_at = Column(String)
    updated_at = Column(String)


class Payments(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer)
    amount = Column(String)
    change_amount = Column(String)
    payment_method = Column(String)
    status = Column(String)  # e.g., "pending", "completed", "failed"
    collected_by = Column(Integer)
    created_at = Column(String)
    updated_at = Column(String)


class SalesReturns(Base):
    __tablename__ = "sales_returns"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, nullable=False, index=True)
    refund_method = Column(String, nullable=False)
    total_refund = Column(String, nullable=False)
    processed_by = Column(Integer)
    created_at = Column(String, nullable=False)


class SalesReturnLines(Base):
    __tablename__ = "sales_return_lines"

    id = Column(Integer, primary_key=True, index=True)
    return_id = Column(Integer, nullable=False, index=True)
    sale_txn_id = Column(Integer, nullable=False, index=True)
    item_id = Column(Integer, nullable=False)
    quantity = Column(String, nullable=False)
    refund_amount = Column(String, nullable=False)


class PaymmetMethods(Base):
    __tablename__ = "payment_methods"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    created_at = Column(String)
    updated_at = Column(String)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    occurred_at = Column(String, nullable=False, index=True)
    actor_id = Column(Integer, index=True)
    actor_name = Column(String)
    action = Column(String, nullable=False, index=True)
    resource_type = Column(String, index=True)
    resource_id = Column(String, index=True)
    ip_address = Column(String)
    outcome = Column(String, nullable=False)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key = Column(String, primary_key=True)
    method = Column(String, nullable=False)
    path = Column(String, nullable=False)
    response_status = Column(Integer, nullable=False)
    response_body = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
