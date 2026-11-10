import asyncio
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database_models import Base, Invoices, Payments, User
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
