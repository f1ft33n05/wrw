import asyncio
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database_models import Base, Contact, Events, Invoices, Item, Payments, SalesTxn
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


def test_sales_history_is_paginated_and_groups_invoice_lines(db):
    customer = Contact(name="History customer", contact_type="customer")
    db.add(customer)
    db.flush()
    older = Invoices(
        customer_id=customer.id,
        status="paid",
        total_price="30.00",
        created_at="2026-11-17T10:00:00+00:00",
    )
    newer = Invoices(
        status="partially_paid",
        total_price="25.00",
        created_at="2026-11-18T10:00:00+00:00",
    )
    draft = Invoices(
        status="draft",
        total_price="100.00",
        created_at="2026-11-19T10:00:00+00:00",
    )
    db.add_all([older, newer, draft])
    db.flush()
    db.add_all([
        SalesTxn(invoice_id=older.id, item_id=1),
        SalesTxn(invoice_id=older.id, item_id=2),
        SalesTxn(invoice_id=newer.id, item_id=3),
        SalesTxn(invoice_id=draft.id, item_id=4),
        Payments(
            invoice_id=newer.id,
            amount="10.00",
            payment_method="cash",
            status="completed",
        ),
    ])
    db.commit()

    first_page = asyncio.run(sales.sales_history(db, offset=0, limit=1))
    second_page = asyncio.run(sales.sales_history(db, offset=1, limit=1))

    assert first_page["sales"] == [{
        "invoice_id": newer.id,
        "invoice_number": f"INV-2026-{newer.id:05d}",
        "receipt_number": f"RCT-2026-{newer.id:05d}",
        "created_at": "2026-11-18T12:00:00+02:00",
        "customer_name": "Walk-in customer",
        "status": "partially_paid",
        "total_amount": "25.00",
        "amount_paid": "10.00",
        "balance_due": "15.00",
        "item_count": 1,
        "payment_methods": ["cash"],
    }]
    assert first_page["next_offset"] == 1
    assert second_page["sales"][0]["invoice_id"] == older.id
    assert second_page["sales"][0]["item_count"] == 2
    assert second_page["next_offset"] is None


def test_receipt_data_returns_snapshot_lines_and_payment_summary(db):
    customer = Contact(name="Receipt customer", contact_type="customer")
    item = Item(name="Current item name")
    db.add_all([customer, item])
    db.flush()
    invoice = Invoices(
        customer_id=customer.id,
        status="paid",
        subtotal="20.00",
        discount_amount="2.00",
        total_price="18.00",
        items=json.dumps([{
            "item_id": item.id,
            "name": "Name at sale time",
            "description": "Sale snapshot",
            "quantity": "2",
            "retail_quantity": "2",
            "retail_unit_price": "10.00",
            "wholesale_quantity": "0",
            "total": "18.00",
        }]),
        created_at="2026-11-18T10:00:00+00:00",
    )
    db.add(invoice)
    db.flush()
    db.add_all([
        SalesTxn(
            invoice_id=invoice.id,
            item_id=item.id,
            quantity="2",
            unit_price="9.00",
            total_price="18.00",
            price_type="retail",
        ),
        Payments(
            invoice_id=invoice.id,
            amount="18.00",
            change_amount="2.00",
            payment_method="cash",
            status="completed",
        ),
    ])
    db.commit()

    receipt = asyncio.run(sales.receipt_data(invoice.id, db))

    assert receipt["invoice_id"] == invoice.id
    assert receipt["customer_name"] == "Receipt customer"
    assert receipt["lines"] == [{
        "name": "Name at sale time",
        "description": "Sale snapshot",
        "quantity": "2",
        "unit_prices": [{
            "quantity": "2",
            "price_type": "retail",
            "unit_price": "10.00",
        }],
        "total": "18.00",
    }]
    assert receipt["payments"][0]["payment_method"] == "cash"
    assert receipt["subtotal"] == "20.00"
    assert receipt["discount_amount"] == "2.00"
    assert receipt["balance_due"] == "0.00"
    assert receipt["change_amount"] == "2.00"
