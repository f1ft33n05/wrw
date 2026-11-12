import asyncio

from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from database_models import Base, Contact, Invoices, Item, ItemCategory, ItemDiscount, SalesTxn
from models import CheckoutRequest, DiscountRequest
from routes import items, sales
from routes.sales import _allocate_discount_to_lines


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


def idempotent_request(key):
    return Request({
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "path": "/sales/create",
        "raw_path": b"/sales/create",
        "query_string": b"",
        "headers": [(b"idempotency-key", key.encode())],
        "server": ("testserver", 80),
        "client": ("testclient", 1234),
        "root_path": "",
    })


def test_discount_module_accepts_customer_targets():
    discount = DiscountRequest(
        name="Loyal customer",
        discount_type="customer",
        target_id=12,
        percentage=Decimal("5"),
    )

    assert discount.discount_type == "customer"


def test_discount_module_saves_customer_targets(db):
    customer = Contact(name="Loyal customer", contact_type="customer")
    db.add(customer)
    db.commit()
    request = DiscountRequest(
        name="Customer rate",
        discount_type="customer",
        target_id=customer.id,
        percentage=Decimal("5"),
    )

    asyncio.run(items.create_discount(request, db))

    stored = db.query(ItemDiscount).filter_by(discount_type="customer").one()
    assert stored.target_id == customer.id


def test_checkout_requires_valid_manual_discount_values():
    base = {
        "items": [{"item_id": 1, "quantity": 1}],
        "amount_paid": 0,
    }

    with pytest.raises(ValidationError):
        CheckoutRequest(**base, discount_mode="percentage")
    with pytest.raises(ValidationError):
        CheckoutRequest(**base, discount_mode="percentage", discount_value=101)

    checkout = CheckoutRequest(
        **base,
        discount_mode="amount",
        discount_value=Decimal("2.50"),
    )
    assert checkout.discount_value == Decimal("2.50")


def test_fixed_sale_discount_is_allocated_across_invoice_lines():
    lines = [
        {"subtotal": "10.01", "quantity": "1"},
        {"subtotal": "9.99", "quantity": "1"},
    ]

    _allocate_discount_to_lines(lines, Decimal("20.00"), Decimal("2.00"))

    assert [line["discount_amount"] for line in lines] == ["1.00", "1.00"]
    assert [line["total"] for line in lines] == ["9.01", "8.99"]
    assert sum(Decimal(line["total"]) for line in lines) == Decimal("18.00")


def test_checkout_manual_customer_and_item_discounts(db):
    category = ItemCategory(name="Wine")
    customer = Contact(name="Loyal customer", contact_type="customer")
    db.add_all([category, customer])
    db.flush()
    item = Item(
        name="Red wine",
        category_id=category.id,
        selling_price_retail="100.00",
        selling_price_wholesale="80.00",
        wholesale_threshold="6",
        quantity="50",
    )
    db.add(item)
    db.flush()
    db.add_all([
        ItemDiscount(
            name="Item rate",
            discount_type="item",
            target_id=item.id,
            percentage="10",
            active=1,
        ),
        ItemDiscount(
            name="Category rate",
            discount_type="category",
            target_id=category.id,
            percentage="15",
            active=1,
        ),
        ItemDiscount(
            name="Customer rate",
            discount_type="customer",
            target_id=customer.id,
            percentage="20",
            active=1,
        ),
    ])
    db.commit()

    def create_checkout(key, mode="automatic", value=None, customer_id=None):
        checkout = CheckoutRequest(
            customer_id=customer_id,
            items=[{"item_id": item.id, "quantity": 1}],
            amount_paid=0,
            discount_mode=mode,
            discount_value=value,
        )
        asyncio.run(sales.create_sale(
            checkout,
            db,
            {"id": 1},
            idempotent_request(key),
        ))
        db.expire_all()
        return db.query(Invoices).order_by(Invoices.id.desc()).first()

    manual = create_checkout(
        "manual-sale-discount",
        mode="percentage",
        value=Decimal("5"),
        customer_id=customer.id,
    )
    assert Decimal(manual.subtotal) == Decimal("100.00")
    assert Decimal(manual.discount_amount) == Decimal("5.00")
    assert Decimal(manual.total_price) == Decimal("95.00")

    customer_sale = create_checkout(
        "customer-auto-discount",
        customer_id=customer.id,
    )
    assert Decimal(customer_sale.discount_amount) == Decimal("20.00")
    assert Decimal(customer_sale.total_price) == Decimal("80.00")

    item_sale = create_checkout("item-auto-discount")
    assert Decimal(item_sale.discount_amount) == Decimal("10.00")
    assert Decimal(item_sale.total_price) == Decimal("90.00")
    assert Decimal(db.query(SalesTxn).order_by(SalesTxn.id.desc()).first().total_price) == Decimal("90.00")

    fixed_sale = create_checkout(
        "fixed-sale-discount",
        mode="amount",
        value=Decimal("12"),
    )
    assert Decimal(fixed_sale.discount_amount) == Decimal("12.00")
    assert Decimal(fixed_sale.total_price) == Decimal("88.00")
