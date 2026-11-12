import asyncio
import json
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database_models import Base, Invoices, Payments, SalesTxn, User
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


@pytest.mark.parametrize(
    ("invoice_cashier_id", "expected_cashier"),
    [(1, "Original Cashier"), (None, "Other Collector")],
)
def test_receipt_shows_one_invoice_cashier_for_multiple_payments(
    db,
    monkeypatch,
    invoice_cashier_id,
    expected_cashier,
):
    cashier = User(id=1, name="Original Cashier", username="cashier", role="cashier")
    other_collector = User(id=2, name="Other Collector", username="collector", role="cashier")
    invoice = Invoices(
        customer_id=None,
        created_by=invoice_cashier_id,
        items=json.dumps([]),
        total_price="100",
        status="paid",
        created_at="2026-11-10T10:00:00+00:00",
    )
    db.add_all([cashier, other_collector, invoice])
    db.flush()
    db.add_all([
        Payments(
            invoice_id=invoice.id,
            amount="50",
            payment_method="cash",
            status="completed",
            collected_by=2,
            created_at="2026-11-10T10:01:00+00:00",
        ),
        Payments(
            invoice_id=invoice.id,
            amount="50",
            payment_method="cash",
            status="completed",
            collected_by=1,
            created_at="2026-11-10T10:02:00+00:00",
        ),
    ])
    db.commit()
    monkeypatch.setattr(
        sales.templates,
        "TemplateResponse",
        lambda request, template_name, context: context,
    )

    context = asyncio.run(
        sales.receipt(invoice.id, None, {"name": "Viewer"}, db)
    )

    assert context["cashier"] == expected_cashier
    assert all("collector" not in payment for payment in context["payments"])


def test_receipt_shows_the_unit_price_used_for_the_sale(db, monkeypatch):
    invoice = Invoices(
        items=json.dumps([{
            "item_id": 1,
            "name": "Wine",
            "quantity": "2",
            "unit_prices": "5:10",
            "wholesale_quantity": "1",
            "retail_quantity": "1",
            "wholesale_unit_price": "5",
            "retail_unit_price": "10",
        }]),
        total_price="15.00",
        status="paid",
        created_at="2026-11-10T10:00:00+00:00",
    )
    db.add(invoice)
    db.flush()
    db.add(SalesTxn(
        invoice_id=invoice.id,
        item_id=1,
        quantity="2",
        unit_price="7.50",
        total_price="15.00",
        price_type="mixed",
    ))
    db.commit()
    monkeypatch.setattr(
        sales.templates,
        "TemplateResponse",
        lambda request, template_name, context: context,
    )

    context = asyncio.run(
        sales.receipt(invoice.id, None, {"name": "Viewer"}, db)
    )

    assert context["lines"][0]["unit_prices"] == [
        {
            "quantity": Decimal("1"),
            "price_type": "wholesale",
            "unit_price": "5",
        },
        {
            "quantity": Decimal("1"),
            "price_type": "retail",
            "unit_price": "10",
        },
    ]
