from datetime import datetime, timezone
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
import database_models
from database_models import User, Contact
from typing import Annotated
from fastapi import Depends


db_url = "postgresql://postgres:bstar1234@localhost:5432/wrw_db"

engine = create_engine(db_url)

session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

install_date = datetime.now(timezone.utc)

seed_data = [
    User(name="Admin", username="admin", password="$2b$12$nkfCnkzJOc3eBWekSr/dAO1di/aJvFVOdGQBbm2if.hmeZNpTOvue", email="f1ft33n05@gmail.com", phone="1234567890", role="admin", created_at=install_date, updated_at=install_date),
    Contact(name="Walkin Customer", email="walkincustomer@wrw.com", phone="0987654321", contact_type="customer", address="Area 1, Lilongwe.", outstanding_balance=0, created_at=install_date, updated_at=install_date)
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
    count = db.query(database_models.User).count()
    if count == 0:
        for item in seed_data:
            db.add(item)
        db.commit()
    db.close()