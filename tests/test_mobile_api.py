import asyncio
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from config import APP_TIMEZONE
from database_models import (
    Base,
    EventStockAllocation,
    Events,
    Invoices,
    Item,
    Payments,
    SalesTxn,
    User,
)
from models import ProfileUpdateRequest
from routes.account import mobile_profile, update_mobile_profile
from routes.events import active_events
from routes.items import list_catalogue
from routes.sales import mobile_dashboard, mobile_sales_report, sales_history


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


def test_mobile_profile_reads_and_updates_only_current_user(db):
    user = User(
        name="Cashier",
        username="cashier",
        email="cashier@example.com",
        phone="123",
        role="cashier",
    )
    db.add(user)
    db.commit()
    current_user = {"id": user.id}

    profile = asyncio.run(mobile_profile(current_user, db))
    updated = asyncio.run(update_mobile_profile(
        ProfileUpdateRequest(
            name="  Alex Cashier  ",
            email=" ALEX@example.com ",
            phone=" 456 ",
        ),
        current_user,
        db,
    ))

    assert profile["username"] == "cashier"
    assert updated["name"] == "Alex Cashier"
    assert updated["email"] == "alex@example.com"
    assert updated["phone"] == "456"
    assert updated["role"] == "cashier"


def test_mobile_profile_rejects_another_users_email(db):
    first = User(username="one", name="One", email="one@example.com", role="cashier")
    second = User(username="two", name="Two", email="two@example.com", role="cashier")
    db.add_all([first, second])
    db.commit()

    with pytest.raises(HTTPException) as error:
        asyncio.run(update_mobile_profile(
            ProfileUpdateRequest(name="One", email="two@example.com", phone=None),
            {"id": first.id},
            db,
        ))

    assert error.value.status_code == 409


def test_active_events_excludes_planned_and_expired_events(db):
    now = datetime.now(APP_TIMEZONE)
    active = Events(
        name="Today event",
        starts_at=datetime.combine(now.date(), time.min, tzinfo=APP_TIMEZONE).isoformat(),
        ends_at=datetime.combine(
            now.date(), time(23, 59, 59), tzinfo=APP_TIMEZONE
        ).isoformat(),
        status="active",
    )
    planned = Events(
        name="Planned event",
        starts_at=datetime.combine(
            now.date(), time(23, 0), tzinfo=APP_TIMEZONE
        ).isoformat(),
        ends_at=active.ends_at,
        status="planned",
    )
    old = Events(
        name="Old event",
        starts_at=(now - timedelta(days=2)).isoformat(),
        ends_at=(now - timedelta(days=1)).isoformat(),
        status="active",
    )
    db.add_all([active, planned, old])
    db.commit()

    result = asyncio.run(active_events(db))

    assert result == [{
        "id": active.id,
        "name": "Today event",
        "venue": None,
        "starts_at": active.starts_at,
    }]
    assert db.query(Events).filter(Events.id == old.id).one().status == "closed"


def test_event_catalogue_uses_remaining_allocated_stock(db):
    now = datetime.now(APP_TIMEZONE)
    event = Events(
        name="Today event",
        starts_at=datetime.combine(now.date(), time.min, tzinfo=APP_TIMEZONE).isoformat(),
        ends_at=datetime.combine(
            now.date(), time(23, 59, 59), tzinfo=APP_TIMEZONE
        ).isoformat(),
        status="active",
    )
    item = Item(
        name="Allocated item",
        barcode="A1",
        purchase_price="1",
        selling_price_wholesale="8",
        selling_price_retail="10",
        wholesale_threshold="6",
        quantity="20",
        unit="bottle",
        description="",
    )
    db.add_all([event, item])
    db.flush()
    db.add(EventStockAllocation(
        event_id=event.id,
        item_id=item.id,
        quantity="5",
        quantity_remaining="3",
        status="active",
    ))
    db.commit()

    result = list_catalogue(db, event.id)

    assert len(result) == 1
    assert result[0].quantity == Decimal("3")


def test_mobile_dashboard_returns_local_day_totals_and_ten_recent_sales(db):
    now = datetime.now(timezone.utc)
    invoices = []
    for index in range(11):
        invoice = Invoices(
            status="paid",
            total_price=str(index + 1),
            created_at=(now - timedelta(minutes=index)).isoformat(),
        )
        db.add(invoice)
        db.flush()
        db.add(SalesTxn(invoice_id=invoice.id, item_id=index + 1))
        db.add(Payments(
            invoice_id=invoice.id,
            amount="5.00",
            status="completed",
            created_at=now.isoformat(),
        ))
        invoices.append(invoice)
    yesterday = Invoices(
        status="paid",
        total_price="100.00",
        created_at=(now - timedelta(days=1)).isoformat(),
    )
    db.add(yesterday)
    db.flush()
    db.add_all([
        SalesTxn(invoice_id=yesterday.id, item_id=99),
        Payments(
            invoice_id=yesterday.id,
            amount="100.00",
            status="completed",
            created_at=(now - timedelta(days=1)).isoformat(),
        ),
    ])
    db.add(Payments(
        invoice_id=invoices[0].id,
        amount="1.00",
        status="completed",
        created_at=now.isoformat(),
    ))
    db.commit()

    result = asyncio.run(mobile_dashboard(db))

    assert result["total_paid_today"] == str(Decimal("56.00"))
    assert result["transaction_count_today"] == 11
    assert len(result["recent_sales"]) == 10
    assert result["recent_sales"][0]["invoice_id"] == invoices[0].id


def test_mobile_sales_report_filters_period_and_groups_payments_and_items(db):
    item = Item(name="Pinotage")
    db.add(item)
    db.flush()
    invoice = Invoices(
        status="paid",
        total_price="140.00",
        tax_amount="20.00",
        created_at="2026-11-18T10:00:00+02:00",
    )
    outside_period = Invoices(
        status="paid",
        total_price="90.00",
        created_at="2026-11-17T10:00:00+02:00",
    )
    db.add_all([invoice, outside_period])
    db.flush()
    db.add_all([
        SalesTxn(
            invoice_id=invoice.id,
            item_id=item.id,
            quantity="2",
            price_type="retail",
            total_price="100.00",
        ),
        SalesTxn(
            invoice_id=invoice.id,
            item_id=item.id,
            quantity="1",
            price_type="wholesale",
            total_price="40.00",
        ),
        SalesTxn(invoice_id=outside_period.id, item_id=item.id, quantity="1"),
        Payments(
            invoice_id=invoice.id,
            amount="100.00",
            payment_method="cash",
            status="completed",
        ),
        Payments(
            invoice_id=invoice.id,
            amount="40.00",
            payment_method="card",
            status="completed",
        ),
    ])
    db.commit()

    report = asyncio.run(mobile_sales_report(
        db,
        {"name": "Cashier Casey"},
        date(2026, 11, 18),
        date(2026, 11, 18),
    ))

    assert report["cashier_name"] == "Cashier Casey"
    assert report["transaction_count"] == 1
    assert report["total_sales"] == "140.00"
    assert report["vat"] == "20.00"
    assert report["payment_methods"] == [
        {"payment_method": "Card", "transaction_count": 1, "amount": "40.00"},
        {"payment_method": "Cash", "transaction_count": 1, "amount": "100.00"},
    ]
    assert report["items_sold"] == [
        {
            "item_name": "Pinotage",
            "price_type": "Retail",
            "quantity": "2",
            "total_amount": "100.00",
        },
        {
            "item_name": "Pinotage",
            "price_type": "Wholesale",
            "quantity": "1",
            "total_amount": "40.00",
        },
    ]
    history = asyncio.run(sales_history(
        db,
        offset=0,
        limit=50,
        date_from=date(2026, 11, 18),
        date_to=date(2026, 11, 18),
    ))
    assert [sale["invoice_id"] for sale in history["sales"]] == [invoice.id]


def test_mobile_sales_report_rejects_reversed_period(db):
    with pytest.raises(HTTPException) as error:
        asyncio.run(mobile_sales_report(
            db,
            {"name": "Cashier Casey"},
            date(2026, 11, 19),
            date(2026, 11, 18),
        ))

    assert error.value.status_code == 422
