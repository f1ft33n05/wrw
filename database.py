from datetime import datetime, timezone
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
import database_models
from database_models import User, Contact
from typing import Annotated
from fastapi import Depends
from passlib.context import CryptContext
from config import (
    ADMIN_EMAIL,
    ADMIN_NAME,
    ADMIN_PASSWORD,
    ADMIN_PHONE,
    ADMIN_USERNAME,
    DATABASE_URL,
    DEFAULT_CUSTOMER_ADDRESS,
    DEFAULT_CUSTOMER_EMAIL,
    DEFAULT_CUSTOMER_NAME,
    DEFAULT_CUSTOMER_PHONE,
)

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


db_url = "postgresql://postgres:bstar1234@localhost:5432/wrw_db"

db_url = DATABASE_URL
engine = create_engine(db_url)

session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

install_date = datetime.now(timezone.utc)

seed_data = [
    User(name="Admin", username="admin", password="$2b$12$nkfCnkzJOc3eBWekSr/dAO1di/aJvFVOdGQBbm2if.hmeZNpTOvue", email="f1ft33n05@gmail.com", phone="1234567890", role="admin", created_at=install_date, updated_at=install_date),
    Contact(name="Walkin Customer", email="walkincustomer@wrw.com", phone="0987654321", contact_type="customer", address="Area 1, Lilongwe.", outstanding_balance=0, created_at=install_date, updated_at=install_date)
]

seed_data = [
    User(name=ADMIN_NAME, username=ADMIN_USERNAME, password=password_context.hash(ADMIN_PASSWORD or "ChangeMe-Not-For-Production-123"), email=ADMIN_EMAIL, phone=ADMIN_PHONE, role="admin", created_at=install_date, updated_at=install_date),
    Contact(name=DEFAULT_CUSTOMER_NAME, email=DEFAULT_CUSTOMER_EMAIL, phone=DEFAULT_CUSTOMER_PHONE, contact_type="customer", address=DEFAULT_CUSTOMER_ADDRESS, outstanding_balance=0, created_at=install_date, updated_at=install_date),
]

def get_db():
    db = session()
    try:
        yield db
    finally:
        db.close()
        
db_dependency = Annotated[Session, Depends(get_db)]

def ensure_sales_columns(database_engine: Engine) -> None:
    document_columns = {
        "document_number": "VARCHAR",
        "issue_date": "VARCHAR",
        "due_date": "VARCHAR",
        "expiry_date": "VARCHAR",
        "notes": "VARCHAR",
        "subtotal": "VARCHAR",
        "tax_rate": "VARCHAR",
        "tax_amount": "VARCHAR",
        "discount_amount": "VARCHAR",
        "currency": "VARCHAR",
        "created_by": "INTEGER",
        "event_id": "INTEGER",
    }
    for table in ("quotations", "invoices"):
        if inspect(database_engine).has_table(table):
            existing = {column["name"] for column in inspect(database_engine).get_columns(table)}
            applicable = dict(document_columns)
            if table != "quotations":
                applicable.pop("expiry_date")
            missing = {name: sql_type for name, sql_type in applicable.items() if name not in existing}
            if missing:
                with database_engine.begin() as connection:
                    for name, sql_type in missing.items():
                        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))
    inspector = inspect(database_engine)
    if inspector.has_table("sales_txns"):
        columns = {column["name"] for column in inspector.get_columns("sales_txns")}
        missing_columns = {
            "item_id": "INTEGER",
            "unit_price": "VARCHAR",
            "price_type": "VARCHAR",
        }
        with database_engine.begin() as connection:
            for name, column_type in missing_columns.items():
                if name not in columns:
                    connection.execute(
                        text(f"ALTER TABLE sales_txns ADD COLUMN {name} {column_type}")
                    )
    if inspector.has_table("payments"):
        columns = {column["name"] for column in inspector.get_columns("payments")}
        missing_columns = {
            "collected_by": "INTEGER",
            "change_amount": "VARCHAR",
        }
        with database_engine.begin() as connection:
            for name, column_type in missing_columns.items():
                if name not in columns:
                    connection.execute(
                        text(f"ALTER TABLE payments ADD COLUMN {name} {column_type}")
                    )
    if inspector.has_table("items"):
        columns = {column["name"] for column in inspector.get_columns("items")}
        with database_engine.begin() as connection:
            if "wholesale_threshold" not in columns:
                connection.execute(
                    text(
                        "ALTER TABLE items ADD COLUMN wholesale_threshold "
                        "VARCHAR NOT NULL DEFAULT '6'"
                    )
                )
            if "category_id" not in columns:
                connection.execute(text("ALTER TABLE items ADD COLUMN category_id INTEGER"))

    if inspector.has_table("sales_txns"):
        columns = {column["name"] for column in inspector.get_columns("sales_txns")}
        with database_engine.begin() as connection:
            for name in ("discount_percentage", "discount_amount"):
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE sales_txns ADD COLUMN {name} VARCHAR"))

    if inspector.has_table("reseller_reconciliations"):
        columns = {
            column["name"]
            for column in inspector.get_columns("reseller_reconciliations")
        }
        with database_engine.begin() as connection:
            if "reconciliation_date" not in columns:
                connection.execute(
                    text(
                        "ALTER TABLE reseller_reconciliations "
                        "ADD COLUMN reconciliation_date VARCHAR"
                    )
                )
                connection.execute(
                    text(
                        "UPDATE reseller_reconciliations "
                        "SET reconciliation_date = period || '-01' "
                        "WHERE reconciliation_date IS NULL"
                    )
                )
            connection.execute(
                text(
                    "ALTER TABLE reseller_reconciliations "
                    "DROP CONSTRAINT IF EXISTS uq_reseller_reconciliation_period"
                )
            )

    if inspector.has_table("invoices"):
        columns = {column["name"] for column in inspector.get_columns("invoices")}
        if "event_id" not in columns:
            with database_engine.begin() as connection:
                connection.execute(text("ALTER TABLE invoices ADD COLUMN event_id INTEGER"))

    if inspector.has_table("sales_txns"):
        columns = {column["name"] for column in inspector.get_columns("sales_txns")}
        if "event_id" not in columns:
            with database_engine.begin() as connection:
                connection.execute(text("ALTER TABLE sales_txns ADD COLUMN event_id INTEGER"))

    if inspector.has_table("events"):
        columns = {column["name"] for column in inspector.get_columns("events")}
        missing_columns = {
            "name": "VARCHAR",
            "venue": "VARCHAR",
            "starts_at": "VARCHAR",
            "ends_at": "VARCHAR",
        }
        with database_engine.begin() as connection:
            for name, column_type in missing_columns.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE events ADD COLUMN {name} {column_type}"))


def init_db():
    ensure_sales_columns(engine)
    db = session()
    for user in db.query(User).all():
        if user.password and not user.password.startswith(("$2b$", "$2a$", "$2y$")):
            user.password = password_context.hash(user.password)
    db.commit()
    if db.query(database_models.RoleDefinition).count() == 0:
        module_permissions = {
            "admin": ["dashboard", "users", "contacts", "items", "sales", "events", "quotations", "invoices", "purchases", "reports", "inventory"],
            "manager": ["dashboard", "users", "contacts", "items", "sales", "events", "quotations", "invoices", "purchases", "reports", "inventory"],
            "cashier": ["dashboard", "contacts", "items", "sales", "events", "quotations", "invoices", "inventory"],
        }
        for role_name, modules in module_permissions.items():
            role = database_models.RoleDefinition(
                name=role_name,
                description=f"{role_name.title()} role",
                system_role=1,
                created_at=install_date.isoformat(),
                updated_at=install_date.isoformat(),
            )
            db.add(role)
            db.flush()
            for module in modules:
                db.add(database_models.RolePermission(
                    role_name=role_name,
                    module=module,
                    can_view=1,
                    can_create=1 if role_name != "cashier" or module in {"sales"} else 0,
                    can_edit=1 if role_name != "cashier" else 0,
                    can_delete=1 if role_name == "admin" else 0,
                    created_at=install_date.isoformat(),
                    updated_at=install_date.isoformat(),
                ))
        db.commit()
    count = db.query(database_models.User).count()
    if count == 0:
        for item in seed_data:
            db.add(item)
        db.commit()
    db.close()