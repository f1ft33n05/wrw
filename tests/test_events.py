import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database_models import (
    Base,
    EventStockAllocation,
    Events,
    Invoices,
    Item,
    SalesTxn,
    StockMvt,
)
from routes.events import archive_event, delete_event


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


def create_event(db):
    event = Events(name="Test event", status="planned")
    db.add(event)
    db.commit()
    return event


@pytest.mark.parametrize("linked_model", [SalesTxn, Invoices])
def test_linked_event_cannot_be_deleted(db, linked_model):
    event = create_event(db)
    db.add(linked_model(event_id=event.id))
    db.commit()

    with pytest.raises(HTTPException) as error:
        asyncio.run(delete_event(event.id, db))

    assert error.value.status_code == 409
    assert db.query(Events).filter(Events.id == event.id).first() is not None


def test_delete_event_returns_remaining_allocated_stock(db):
    event = create_event(db)
    item = Item(name="Test item", quantity="8")
    db.add(item)
    db.commit()
    db.add(
        EventStockAllocation(
            event_id=event.id,
            item_id=item.id,
            quantity="5",
            quantity_remaining="3",
            status="active",
        )
    )
    db.commit()

    asyncio.run(delete_event(event.id, db))

    assert db.query(Events).filter(Events.id == event.id).first() is None
    assert db.query(EventStockAllocation).filter(EventStockAllocation.event_id == event.id).count() == 0
    assert db.query(Item).filter(Item.id == item.id).one().quantity == "11"
    assert db.query(StockMvt).filter(StockMvt.item_id == item.id).one().quantity == "3"


def test_archive_event_marks_status(db):
    event = create_event(db)
    item = Item(name="Test item", quantity="8")
    db.add(item)
    db.commit()
    db.add(
        EventStockAllocation(
            event_id=event.id,
            item_id=item.id,
            quantity="5",
            quantity_remaining="3",
            status="active",
        )
    )
    db.commit()

    result = asyncio.run(archive_event(event.id, db))

    assert result == {"message": "Event archived"}
    assert db.query(Events).filter(Events.id == event.id).one().status == "archived"
    allocation = db.query(EventStockAllocation).filter(EventStockAllocation.event_id == event.id).one()
    assert allocation.status == "returned"
    assert allocation.quantity_remaining == "0"
    assert db.query(Item).filter(Item.id == item.id).one().quantity == "11"


def test_delete_event_without_sales_succeeds(db):
    event = create_event(db)

    result = asyncio.run(delete_event(event.id, db))

    assert result == {"message": "Event deleted"}
    assert db.query(Events).filter(Events.id == event.id).first() is None
