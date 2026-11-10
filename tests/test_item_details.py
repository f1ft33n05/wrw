import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database_models import Base, Item, PurchaseLines, Purchases
from routes.items import item_details


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


def test_item_details_includes_purchase_history(db):
    item = Item(name="Test item", quantity="4", purchase_price="3")
    purchase = Purchases(
        supplier_id=1,
        total_amount="12",
        created_at="2026-11-10T00:00:00+02:00",
    )
    db.add_all([item, purchase])
    db.commit()
    db.add(
        PurchaseLines(
            purchase_id=purchase.id,
            item_id=item.id,
            quantity="4",
            unit_cost="3",
            total_amount="12",
        )
    )
    db.commit()

    details = asyncio.run(item_details(item.id, db))

    assert details["item"]["id"] == item.id
    assert details["purchases"] == [
        {
            "id": db.query(PurchaseLines).one().id,
            "purchase_id": purchase.id,
            "quantity": "4",
            "unit_cost": "3",
            "total_amount": "12",
            "created_at": "2026-11-10T00:00:00+02:00",
        }
    ]
