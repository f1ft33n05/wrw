import json
import asyncio

from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from database_models import (
    Base,
    EventStockAllocation,
    Events,
    Invoices,
    Item,
    Payments,
    SalesReturnLines,
    SalesReturns,
    SalesTxn,
    User,
)
from models import SaleReturnRequest
from routes import auth, sales


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


def return_request(key: str) -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "path": "/sales/returns",
        "raw_path": b"/sales/returns",
        "query_string": b"",
        "headers": [(b"idempotency-key", key.encode())],
        "server": ("testserver", 80),
        "client": ("testclient", 1234),
        "root_path": "",
    })


def add_sale(db, *, event_id=None, quantity="2", amount="18.00", payment="18.00"):
    item = Item(
        name="Bottle",
        selling_price_retail="10.00",
        selling_price_wholesale="9.00",
        quantity="3",
        wholesale_threshold="6",
    )
    invoice = Invoices(
        event_id=event_id,
        total_price=amount,
        status="paid",
        created_at="2025-01-01T10:00:00+00:00",
    )
    db.add_all([item, invoice])
    db.flush()
    sale_line = SalesTxn(
        invoice_id=invoice.id,
        event_id=event_id,
        item_id=item.id,
        quantity=quantity,
        unit_price=str(Decimal(amount) / Decimal(quantity)),
        total_price=amount,
        created_at=invoice.created_at,
    )
    db.add_all([
        sale_line,
        Payments(
            invoice_id=invoice.id,
            amount=payment,
            payment_method="cash",
            status="completed",
        ),
    ])
    db.commit()
    return item, invoice, sale_line


def test_sale_return_uses_discounted_amount_and_prevents_over_return(db):
    item, invoice, sale_line = add_sale(db)
    user = {"id": 7, "role": "cashier"}

    first = asyncio.run(sales.create_sale_return(
        SaleReturnRequest(
            invoice_id=invoice.id,
            refund_method="cash",
            items=[{"sale_txn_id": sale_line.id, "quantity": "1"}],
        ),
        db,
        user,
        return_request("return-1"),
    ))
    assert json.loads(first.body)["refund_amount"] == "9.00"
    assert item.quantity == "4"
    assert db.query(SalesReturnLines).one().refund_amount == "9.00"

    asyncio.run(sales.create_sale_return(
        SaleReturnRequest(
            invoice_id=invoice.id,
            refund_method="cash",
            items=[{"sale_txn_id": sale_line.id, "quantity": "1"}],
        ),
        db,
        user,
        return_request("return-2"),
    ))
    assert db.query(SalesReturns).count() == 2
    assert item.quantity == "5"

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(sales.create_sale_return(
            SaleReturnRequest(
                invoice_id=invoice.id,
                refund_method="cash",
                items=[{"sale_txn_id": sale_line.id, "quantity": "1"}],
            ),
            db,
            user,
            return_request("return-3"),
        ))
    assert exc_info.value.status_code == 409


def test_event_sale_return_replenishes_event_allocation(db):
    event = Events(
        name="Market",
        starts_at="2099-01-01T10:00:00+00:00",
        ends_at="2099-01-01T18:00:00+00:00",
        status="active",
    )
    db.add(event)
    db.flush()
    item, invoice, sale_line = add_sale(db, event_id=event.id)
    allocation = EventStockAllocation(
        event_id=event.id,
        item_id=item.id,
        quantity="5",
        quantity_remaining="0",
        status="sold",
    )
    db.add(allocation)
    db.commit()

    asyncio.run(sales.create_sale_return(
        SaleReturnRequest(
            invoice_id=invoice.id,
            refund_method="card",
            items=[{"sale_txn_id": sale_line.id, "quantity": "1"}],
        ),
        db,
        {"id": 3, "role": "cashier"},
        return_request("event-return-1"),
    ))

    assert allocation.quantity_remaining == "1"
    assert allocation.status == "active"
    assert item.quantity == "3"


def test_sale_return_cannot_refund_more_than_collected(db):
    item, invoice, sale_line = add_sale(db, amount="18.00", payment="8.00")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(sales.create_sale_return(
            SaleReturnRequest(
                invoice_id=invoice.id,
                refund_method="cash",
                items=[{"sale_txn_id": sale_line.id, "quantity": "1"}],
            ),
            db,
            {"id": 3, "role": "cashier"},
            return_request("unpaid-return"),
        ))

    assert exc_info.value.status_code == 409
    assert item.quantity == "3"
    assert db.query(SalesReturns).count() == 0


def test_pos_resume_is_scoped_to_the_draft_owner(db, monkeypatch):
    draft = Invoices(
        created_by=8,
        items=json.dumps([{
            "item_id": 1,
            "quantity": "1",
            "price_type": "retail",
        }]),
        total_price="10.00",
        status="draft",
    )
    db.add(draft)
    db.commit()
    monkeypatch.setattr(
        sales.templates,
        "TemplateResponse",
        lambda request, template_name, context: context,
    )
    request = Request({
        "type": "http",
        "method": "GET",
        "scheme": "http",
        "path": "/sales/pos",
        "raw_path": b"/sales/pos",
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "client": ("testclient", 1234),
        "root_path": "",
    })

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(sales.pos_screen(
            request,
            {"id": 9, "role": "cashier"},
            db,
            resume_draft_id=draft.id,
        ))
    assert exc_info.value.status_code == 404

    context = asyncio.run(sales.pos_screen(
        request,
        {"id": 8, "role": "cashier"},
        db,
        resume_draft_id=draft.id,
    ))
    assert context["resume_draft_id"] == draft.id
    assert [sale["id"] for sale in context["drafts"]] == [draft.id]


def test_legacy_pos_drafts_are_recognized_without_price_type():
    legacy_draft = Invoices(
        items=json.dumps([{"item_id": 1, "quantity": "1", "unit_price": "10.00"}]),
        status="draft",
    )
    document_draft = Invoices(
        document_number="INV-100",
        items=json.dumps([{"item_id": 1, "quantity": "1", "unit_price": "10.00"}]),
        status="draft",
    )

    assert sales.is_pos_draft_invoice(legacy_draft)
    assert not sales.is_pos_draft_invoice(document_draft)


def test_html_user_context_exposes_the_latest_pos_draft(db, monkeypatch):
    user = User(name="Cashier", username="cashier", role="cashier")
    db.add(user)
    db.flush()
    draft = Invoices(
        created_by=user.id,
        items=json.dumps([{"item_id": 1, "quantity": "1"}]),
        status="draft",
    )
    db.add(draft)
    db.commit()
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda token, secret, algorithms: {"sub": user.username, "id": user.id},
    )
    request = Request({
        "type": "http",
        "method": "GET",
        "scheme": "http",
        "path": "/sales/returns",
        "raw_path": b"/sales/returns",
        "query_string": b"",
        "headers": [(b"accept", b"text/html")],
        "server": ("testserver", 80),
        "client": ("testclient", 1234),
        "root_path": "",
    })

    current_user = asyncio.run(auth.get_current_user(request, "test-token", db))

    assert current_user["paused_pos_draft_id"] == draft.id
