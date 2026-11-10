from datetime import datetime, timezone
from decimal import Decimal

from database_models import EventStockAllocation, Events, Item, StockMvt


def parse_event_timestamp(value: str | None):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if len(value) == 10:
        parsed = parsed.replace(hour=23, minute=59, second=59)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_event_start_timestamp(value: str | None):
    if value and len(value) == 10:
        value = f"{value}T00:00:00"
    return parse_event_timestamp(value)


def parse_event_end_timestamp(starts_at: str | None, ends_at: str | None):
    if ends_at:
        return parse_event_timestamp(ends_at)
    if not starts_at or len(starts_at) == 10:
        return parse_event_timestamp(starts_at)
    try:
        parsed = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=0)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def event_is_expired(event: Events, now: datetime | None = None) -> bool:
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    ends_at = parse_event_end_timestamp(event.starts_at, event.ends_at)
    return ends_at is not None and ends_at < current_time


def return_expired_event_stock(db, now: datetime | None = None) -> list[dict]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    timestamp = now.isoformat()

    events = db.query(Events).filter(Events.status.in_(["planned", "active"])).all()
    status_changed = False
    for event in events:
        ends_at = parse_event_end_timestamp(event.starts_at, event.ends_at)
        if ends_at is not None and ends_at < now:
            event.status = "closed"
            event.updated_at = timestamp
            status_changed = True
            continue
        starts_at = parse_event_start_timestamp(event.starts_at)
        if event.status == "planned" and starts_at is not None and starts_at <= now:
            event.status = "active"
            event.updated_at = timestamp
            status_changed = True

    allocations = db.query(EventStockAllocation).filter(
        EventStockAllocation.status == "active",
        EventStockAllocation.quantity_remaining != "0",
    ).with_for_update().all()
    returned = []

    for allocation in allocations:
        event = db.query(Events).filter(Events.id == allocation.event_id).with_for_update().first()
        if event is None:
            continue
        ends_at = parse_event_end_timestamp(event.starts_at, event.ends_at)
        if ends_at is None or ends_at >= now:
            continue

        remaining = Decimal(allocation.quantity_remaining)
        if remaining <= 0:
            continue
        item = db.query(Item).filter(Item.id == allocation.item_id).with_for_update().first()
        if item is None:
            continue
        item.quantity = str(Decimal(item.quantity or "0") + remaining)
        item.updated_at = timestamp
        allocation.quantity_remaining = "0"
        allocation.status = "returned"
        allocation.updated_at = timestamp
        db.add(StockMvt(
            item_id=item.id,
            quantity=str(remaining),
            movement_type="in",
            note=f"Returned from Event ({event.id})",
            created_at=timestamp,
            updated_at=timestamp,
        ))
        returned.append({"event_id": event.id, "item_id": item.id, "quantity": str(remaining)})

    if returned or status_changed:
        db.commit()
        db.expire_all()
    return returned
