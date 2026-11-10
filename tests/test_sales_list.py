import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database_models import Base, Contact, Events, Invoices, Payments
from routes import sales


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_sales_list_provides_filter_metadata_and_column_totals(db, monkeypatch):
    customer = Contact(name="Test customer", contact_type="customer")
    event = Events(name="Test event", status="active")
    db.add_all([customer, event])
    db.flush()
    invoice = Invoices(
        customer_id=customer.id,
        event_id=event.id,
        status="partial",
        total_price="100.00",
        created_at="2026-11-10T10:00:00+02:00",
    )
    db.add(invoice)
    db.flush()
    db.add_all([
        Payments(
            invoice_id=invoice.id,
            amount="20.00",
            payment_method="cash",
            status="completed",
        ),
        Payments(
            invoice_id=invoice.id,
            amount="30.00",
            payment_method="card",
            status="completed",
        ),
    ])
    db.commit()
    monkeypatch.setattr(
        sales.templates,
        "TemplateResponse",
        lambda request, template_name, context: context,
    )

    context = asyncio.run(sales.sales_list(None, {"name": "Viewer"}, db))

    assert context["sales_totals"] == {
        "total": 100,
        "paid": 50,
        "balance_due": 50,
    }
    assert context["payment_methods"] == ["card", "cash"]
    assert context["customer_options"] == [(str(customer.id), "Test customer")]
    assert context["status_options"] == ["partial"]
    assert context["sales"][0]["event_id"] == str(event.id)
    assert context["sales"][0]["created_at_iso"].startswith("2026-11-10")
