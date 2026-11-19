from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from config import APP_TIMEZONE
from database import ensure_sales_columns
from database_models import Base, Invoices, Quotations
from document_numbering import display_document_number, next_document_number


def test_document_sequences_are_independent_and_five_digits():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        year = datetime.now(APP_TIMEZONE).year
        invoice = Invoices(
            document_number=f"INV-{year}-00007",
            receipt_number=f"RCT-{year}-00012",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        quotation = Quotations(
            document_number=f"QT-{year}-00003",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        db.add_all([invoice, quotation])
        db.commit()

        assert next_document_number(db, Invoices, "document_number", "INV") == (
            f"INV-{year}-00008"
        )
        assert next_document_number(db, Invoices, "receipt_number", "RCT") == (
            f"RCT-{year}-00013"
        )
        assert next_document_number(db, Quotations, "document_number", "QT") == (
            f"QT-{year}-00004"
        )
    engine.dispose()


def test_document_display_pads_legacy_numbers_and_formats_missing_numbers():
    created_at = "2024-06-01T10:00:00+00:00"

    assert display_document_number("QT-2024-7", "QT", created_at, 99) == (
        "QT-2024-00007"
    )
    assert display_document_number(None, "RCT", created_at, 42) == (
        "RCT-2024-00042"
    )


def test_existing_invoice_table_gets_receipt_number_column_only():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE invoices (id INTEGER PRIMARY KEY, created_at VARCHAR, "
            "document_number VARCHAR)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE quotations (id INTEGER PRIMARY KEY, created_at VARCHAR, "
            "document_number VARCHAR)"
        )

    ensure_sales_columns(engine)

    inspector = inspect(engine)
    assert "receipt_number" in {
        column["name"] for column in inspector.get_columns("invoices")
    }
    assert "receipt_number" not in {
        column["name"] for column in inspector.get_columns("quotations")
    }
    engine.dispose()
