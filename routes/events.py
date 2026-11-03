from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import db_dependency
from database_models import Events, Invoices, Payments
from models import EventRequest, Role
from routes.auth import RoleChecker, get_current_user
from routes.ledger_utils import decimal_value, format_money


router = APIRouter(tags=["events"])
templates = Jinja2Templates(directory="templates")
templates.env.filters["money"] = format_money
user_dependency = Annotated[dict, Depends(get_current_user)]
EVENT_ACCESS = Depends(RoleChecker(Role.admin, Role.manager))
EVENT_VIEW_ACCESS = Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))


@router.get("/events", response_class=HTMLResponse, dependencies=[EVENT_VIEW_ACCESS])
async def events_page(request: Request, user: user_dependency, db: db_dependency):
    events = db.query(Events).order_by(Events.starts_at.desc(), Events.name).all()
    return templates.TemplateResponse(
        request,
        "events.html",
        {"user": user, "events": events},
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


@router.get("/events/{event_id}", response_class=HTMLResponse, dependencies=[EVENT_VIEW_ACCESS])
async def event_detail(event_id: int, request: Request, user: user_dependency, db: db_dependency):
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

