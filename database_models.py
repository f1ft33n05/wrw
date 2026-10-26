from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
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
    quantity = Column(String)
    unit = Column(String)
    created_at = Column(String)
    updated_at = Column(String)

class SalesTxn(Base):
    __tablename__ = "sales_txns"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer)
    invoice_id = Column(Integer, foreign_key="invoices.id")
    quantity = Column(String)
    total_price = Column(String)
    payment_method = Column(String)
    added_by = Column(Integer, foreign_key="users.id")
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
    payment_method = Column(String)
    status = Column(String)  # e.g., "pending", "completed", "failed"
    created_at = Column(String)
    updated_at = Column(String)

class PaymmetMethods(Base):
    __tablename__ = "payment_methods"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    created_at = Column(String)
    updated_at = Column(String)

