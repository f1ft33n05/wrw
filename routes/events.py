from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import db_dependency
from database_models import (
    EventStockAllocation,
    Events,
    Invoices,
    Item,
    Payments,
    Quotations,
    SalesTxn,
    StockMvt,
)
from models import EventRequest, EventStockAllocationRequest, Role
from routes.auth import RoleChecker, get_current_user
from routes.ledger_utils import decimal_value, format_money
from event_stock import parse_event_timestamp, return_expired_event_stock


router = APIRouter(tags=["events"])
templates = Jinja2Templates(directory="templates")
templates.env.filters["money"] = format_money
user_dependency = Annotated[dict, Depends(get_current_user)]
EVENT_ACCESS = Depends(RoleChecker(Role.admin, Role.manager))
EVENT_VIEW_ACCESS = Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))


def _release_event_stock(db, event_id: int, timestamp: str, source: str):
    allocations = (
        db.query(EventStockAllocation)
        .filter(EventStockAllocation.event_id == event_id)
        .with_for_update()
        .all()
    )
    remaining_stock = []
    for allocation in allocations:
        remaining = decimal_value(allocation.quantity_remaining, "remaining event stock")
        if remaining <= 0:
            continue
        item = db.query(Item).filter(Item.id == allocation.item_id).with_for_update().first()
        if item is None:
            raise HTTPException(
                status_code=409,
                detail=f"Allocated item {allocation.item_id} no longer exists; event cannot be {source}",
            )
        remaining_stock.append((allocation, item, remaining))

    for allocation, item, remaining in remaining_stock:
        item.quantity = str(decimal_value(item.quantity or "0", "item quantity") + remaining)
        item.updated_at = timestamp
        allocation.quantity_remaining = "0"
        allocation.status = "returned"
        allocation.updated_at = timestamp
        db.add(
            StockMvt(
                item_id=item.id,
                quantity=str(remaining),
                movement_type="in",
                note=f"Returned from {source} Event ({event_id})",
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
    return allocations


@router.get("/events", response_class=HTMLResponse, dependencies=[EVENT_VIEW_ACCESS])
async def events_page(request: Request, user: user_dependency, db: db_dependency):
    return_expired_event_stock(db)
    events = db.query(Events).order_by(Events.starts_at.desc(), Events.name).all()
    items = db.query(Item).order_by(Item.name).all()
    events_with_sales = {
        row[0]
        for row in db.query(SalesTxn.event_id)
        .filter(SalesTxn.event_id.isnot(None))
        .distinct()
        .all()
    }
    events_with_sales.update(
        row[0]
        for row in db.query(Invoices.event_id)
        .filter(Invoices.event_id.isnot(None))
        .distinct()
        .all()
    )
    return templates.TemplateResponse(
        request,
        "events.html",
        {
            "user": user,
            "events": events,
            "events_with_sales": events_with_sales,
            "stock_items": items,
        },
    )


@router.post("/events", dependencies=[EVENT_ACCESS])
async def create_event(payload: EventRequest, user: user_dependency, db: db_dependency):
    timestamp = datetime.now(timezone.utc).isoformat()
    event = Events(
        name=payload.name.strip(),
        venue=payload.venue.strip() if payload.venue else None,
        starts_at=payload.starts_at or None,
        ends_at=payload.ends_at or None,
        event_type=payload.event_type.strip() if payload.event_type else None,
        description=payload.description.strip() if payload.description else None,
        status=payload.status if payload.status in {"planned", "active", "closed", "cancelled"} else "planned",
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return {"message": "Event created", "event_id": event.id}


@router.delete("/events/{event_id}", dependencies=[EVENT_ACCESS])
async def delete_event(event_id: int, db: db_dependency):
    event = db.query(Events).filter(Events.id == event_id).with_for_update().first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if (
        db.query(SalesTxn.id).filter(SalesTxn.event_id == event_id).first()
        or db.query(Invoices.id).filter(Invoices.event_id == event_id).first()
    ):
        raise HTTPException(
            status_code=409,
            detail="Events linked to sales cannot be deleted; archive the event instead",
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    allocations = _release_event_stock(db, event_id, timestamp, "deleted")
    db.query(Quotations).filter(Quotations.event_id == event_id).update(
        {Quotations.event_id: None, Quotations.updated_at: timestamp},
        synchronize_session=False,
    )
    for allocation in allocations:
        db.delete(allocation)
    db.delete(event)
    db.commit()
    return {"message": "Event deleted"}


@router.patch("/events/{event_id}/archive", dependencies=[EVENT_ACCESS])
async def archive_event(event_id: int, db: db_dependency):
    event = db.query(Events).filter(Events.id == event_id).with_for_update().first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    timestamp = datetime.now(timezone.utc).isoformat()
    _release_event_stock(db, event_id, timestamp, "archived")
    event.status = "archived"
    event.updated_at = timestamp
    db.commit()
    return {"message": "Event archived"}


@router.post("/events/{event_id}/stock", dependencies=[EVENT_ACCESS])
async def allocate_event_stock(
    event_id: int,
    payload: EventStockAllocationRequest,
    user: user_dependency,
    db: db_dependency,
):
    event = db.query(Events).filter(Events.id == event_id).with_for_update().first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.status in {"closed", "cancelled", "archived"}:
        raise HTTPException(status_code=409, detail="Stock cannot be assigned to a closed event")
    ends_at = parse_event_timestamp(event.ends_at or event.starts_at)
    if ends_at is not None and ends_at < datetime.now(timezone.utc):
        event.status = "closed"
        event.updated_at = datetime.now(timezone.utc).isoformat()
        db.commit()
        raise HTTPException(status_code=409, detail="Stock cannot be assigned to a closed event")

    item_ids = [line.item_id for line in payload.allocations]
    if len(set(item_ids)) != len(item_ids):
        raise HTTPException(status_code=422, detail="Each item can only be assigned once")

    timestamp = datetime.now(timezone.utc).isoformat()
    allocated = []
    for line in payload.allocations:
        item = db.query(Item).filter(Item.id == line.item_id).first()
        if item is None:
            raise HTTPException(status_code=404, detail=f"Item {line.item_id} not found")
        quantity = decimal_value(str(line.quantity), "allocation quantity")
        if quantity <= 0:
            raise HTTPException(status_code=422, detail="Allocation quantity must be positive")

        existing = db.query(EventStockAllocation).filter(
            EventStockAllocation.event_id == event_id,
            EventStockAllocation.item_id == item.id,
            EventStockAllocation.status == "active",
        ).first()
        available_quantity = decimal_value(item.quantity or "0", "item quantity")
        if quantity > available_quantity:
            raise HTTPException(status_code=409, detail=f"Insufficient unallocated stock for {item.name}")

        if existing is None:
            db.add(EventStockAllocation(
                event_id=event_id,
                item_id=item.id,
                quantity=str(quantity),
                quantity_remaining=str(quantity),
                status="active",
                allocated_by=user.get("id") if isinstance(user, dict) else getattr(user, "id", None),
                created_at=timestamp,
                updated_at=timestamp,
            ))
        else:
            allocated_quantity = decimal_value(existing.quantity, "allocated quantity") + quantity
            existing.quantity = str(allocated_quantity)
            existing.quantity_remaining = str(decimal_value(existing.quantity_remaining, "remaining quantity") + quantity)
            existing.updated_at = timestamp
        item.quantity = str(available_quantity - quantity)
        item.updated_at = timestamp
        allocated.append({"item_id": item.id, "quantity": str(quantity)})

    db.commit()
    return {"message": "Event stock assigned", "allocations": allocated}


@router.get("/events/{event_id}", response_class=HTMLResponse, dependencies=[EVENT_VIEW_ACCESS])
async def event_detail(event_id: int, request: Request, user: user_dependency, db: db_dependency):
    return_expired_event_stock(db)
    event = db.query(Events).filter(Events.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    invoices = db.query(Invoices).filter(Invoices.event_id == event_id).order_by(Invoices.id.desc()).all()
    invoice_ids = [invoice.id for invoice in invoices]
    payments = (
        db.query(Payments)
        .filter(Payments.invoice_id.in_(invoice_ids), Payments.status == "completed")
        .all()
        if invoice_ids
        else []
    )
    total_sales = sum(
        (decimal_value(invoice.total_price, "invoice total") for invoice in invoices),
        Decimal("0"),
    )
    total_collected = sum(
        (decimal_value(payment.amount, "payment amount") for payment in payments),
        Decimal("0"),
    )
    return templates.TemplateResponse(
        request,
        "event_detail.html",
        {
            "user": user,
            "event": event,
            "invoices": invoices,
            "invoice_count": len(invoices),
            "total_sales": total_sales,
            "total_collected": total_collected,
            "balance_due": max(total_sales - total_collected, Decimal("0")),
        },
    )
