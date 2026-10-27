from sqlalchemy import Column, Integer, String, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base

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
    created_at = Column(String)
    updated_at = Column(String)

class SalesTxn(Base):
    __tablename__ = "sales_txns"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer)
    invoice_id = Column(Integer)
    item_id = Column(Integer)
    quantity = Column(String)
    unit_price = Column(String)
    price_type = Column(String)
    total_price = Column(String)
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
    __table_args__ = (
        UniqueConstraint("reseller_id", "period", name="uq_reseller_reconciliation_period"),
    )

    id = Column(Integer, primary_key=True, index=True)
    reseller_id = Column(Integer, nullable=False, index=True)
    period = Column(String, nullable=False)
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
    created_at = Column(String)
    updated_at = Column(String)

class Events(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String)
    description = Column(String)
    status = Column(String)
    created_at = Column(String)
    updated_at = Column(String)

class Quotations(Base):
    __tablename__ = "quotations"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer)
    items = Column(String)  # JSON string of items, quantities and unit prices
    total_price = Column(String)
    status = Column(String)  # e.g., "pending", "approved", "rejected"
    created_at = Column(String)
    updated_at = Column(String)

class Invoices(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer)
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

class PaymmetMethods(Base):
    __tablename__ = "payment_methods"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    created_at = Column(String)
    updated_at = Column(String)
