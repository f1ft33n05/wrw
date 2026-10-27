from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette import status

from database import db_dependency
from database_models import (
    Contact,
    Item,
    ResellerAllocationLines,
    ResellerAllocations,
    ResellerPayments,
    ResellerReconciliations,
    ResellerReconciliationLines,
    StockMvt,
)
from models import (
    ResellerAllocationRequest,
    ResellerPaymentRequest,
    ResellerReconciliationRequest,
    Role,
)
from routes.auth import RoleChecker, get_current_user
from routes.ledger_utils import (
    decimal_value,
    format_money,
    money,
    validate_payment_method,
)


router = APIRouter(tags=["resellers"])
templates = Jinja2Templates(directory="templates")
templates.env.filters["money"] = format_money
user_dependency = Annotated[dict, Depends(get_current_user)]
RESELLER_ACCESS = Depends(RoleChecker(Role.admin, Role.manager))
APP_TIMEZONE = ZoneInfo("Africa/Harare")


def _display_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(APP_TIMEZONE).strftime("%d/%m/%Y %H:%M")


def _reconciled_total(db, reseller_id: int) -> Decimal:
    rows = (
        db.query(ResellerReconciliations)
        .filter(ResellerReconciliations.reseller_id == reseller_id)
        .all()
    )
    return sum(
        (decimal_value(row.total_due, "reconciliation total") for row in rows),
        Decimal("0"),
    )


def _paid_total(db, reseller_id: int) -> Decimal:
    rows = (
        db.query(ResellerPayments)
        .filter(ResellerPayments.reseller_id == reseller_id)
        .all()
    )
    return sum(
        (decimal_value(row.amount, "reseller payment") for row in rows),
        Decimal("0"),
    )


def _balance_due(db, reseller_id: int) -> Decimal:
    return max(_reconciled_total(db, reseller_id) - _paid_total(db, reseller_id), Decimal("0"))


@router.get(
    "/reseller_pg",
    response_class=HTMLResponse,
    dependencies=[RESELLER_ACCESS],
)
async def reseller_page(
    request: Request,
    user: user_dependency,
    db: db_dependency,
    reseller_id: int | None = None,
):
    resellers = (
        db.query(Contact)
        .filter(Contact.contact_type == "reseller")
        .order_by(Contact.name)
        .all()
    )
    selected = next(
        (reseller for reseller in resellers if reseller.id == reseller_id),
        resellers[0] if reseller_id is None and resellers else None,
    )
    if reseller_id is not None and selected is None:
        raise HTTPException(status_code=404, detail="Reseller not found")

    items = db.query(Item).order_by(Item.name).all()
    holdings = []
    reconciliations = []
    payments = []
    total_due = Decimal("0")
    total_paid = Decimal("0")
    if selected is not None:
        allocation_lines = (
            db.query(ResellerAllocationLines, ResellerAllocations)
            .join(
                ResellerAllocations,
                ResellerAllocations.id == ResellerAllocationLines.allocation_id,
            )
            .filter(
                ResellerAllocations.reseller_id == selected.id,
                ResellerAllocationLines.quantity_remaining != "0",
            )
            .order_by(ResellerAllocations.id, ResellerAllocationLines.id)
            .all()
        )
        item_by_id = {item.id: item for item in items}
        for line, allocation in allocation_lines:
            remaining = decimal_value(line.quantity_remaining, "held quantity")
            if remaining <= 0:
                continue
            item = item_by_id.get(line.item_id)
            holdings.append(
                {
                    "line": line,
                    "allocation": allocation,
                    "item_name": item.name if item else "Unknown item",
                }
            )
        reconciliation_rows = (
            db.query(ResellerReconciliations)
            .filter(ResellerReconciliations.reseller_id == selected.id)
            .order_by(ResellerReconciliations.period.desc())
            .all()
        )
        reconciliation_ids = {row.id for row in reconciliation_rows}
        reconciliation_lines = (
            db.query(ResellerReconciliationLines)
            .filter(
                ResellerReconciliationLines.reconciliation_id.in_(reconciliation_ids)
            )
            .all()
            if reconciliation_ids
            else []
        )
        reconciliation_line_groups: dict[int, list[dict]] = {}
        allocation_line_ids = {
            line.allocation_line_id for line in reconciliation_lines
        }
        allocation_lines_by_id = {
            line.id: line
            for line in (
                db.query(ResellerAllocationLines)
                .filter(ResellerAllocationLines.id.in_(allocation_line_ids))
                .all()
                if allocation_line_ids
                else []
            )
        }
        item_names = {item.id: item.name for item in items}
        for line in reconciliation_lines:
            allocation_line = allocation_lines_by_id.get(line.allocation_line_id)
            reconciliation_line_groups.setdefault(line.reconciliation_id, []).append(
                {
                    "item_name": (
                        item_names.get(allocation_line.item_id, "Unknown item")
                        if allocation_line
                        else "Unknown item"
                    ),
                    "sold": line.quantity_sold,
                    "returned": line.quantity_returned,
                    "unit_price": decimal_value(line.unit_price, "reconciled unit price"),
                    "due": decimal_value(line.total_due, "reconciled line total"),
                }
            )
        reconciliations = [
            {
                "reconciliation": row,
                "total": decimal_value(row.total_due, "reconciliation total"),
                "lines": reconciliation_line_groups.get(row.id, []),
            }
            for row in reconciliation_rows
        ]
        payment_rows = (
            db.query(ResellerPayments)
            .filter(ResellerPayments.reseller_id == selected.id)
            .order_by(ResellerPayments.id.desc())
            .all()
        )
        payments = payment_rows
        total_due = _reconciled_total(db, selected.id)
        total_paid = _paid_total(db, selected.id)

    current_period = datetime.now(APP_TIMEZONE).strftime("%Y-%m")
    return templates.TemplateResponse(
        request,
        "reseller_pg.html",
        {
            "user": user,
            "resellers": resellers,
            "selected_reseller": selected,
            "items": items,
            "holdings": holdings,
            "reconciliations": reconciliations,
            "payments": payments,
            "total_due": total_due,
            "total_paid": total_paid,
            "balance_due": max(total_due - total_paid, Decimal("0")),
            "current_period": current_period,
            "display_timestamp": _display_timestamp,
        },
    )


@router.post(
    "/reseller_pg/allocations",
    status_code=status.HTTP_201_CREATED,
    dependencies=[RESELLER_ACCESS],
)
async def create_reseller_allocation(
    payload: ResellerAllocationRequest,
    db: db_dependency,
    user: user_dependency,
):
    reseller = (
        db.query(Contact)
        .filter(
            Contact.id == payload.reseller_id,
            Contact.contact_type == "reseller",
        )
        .with_for_update()
        .first()
    )
    if reseller is None:
        raise HTTPException(status_code=404, detail="Reseller not found")
    item_ids = {line.item_id for line in payload.items}
    if len(item_ids) != len(payload.items):
        raise HTTPException(status_code=422, detail="Each item may only appear once per allocation")
    items = (
        db.query(Item)
        .filter(Item.id.in_(item_ids))
        .order_by(Item.id)
        .with_for_update()
        .all()
    )
    item_by_id = {item.id: item for item in items}
    missing_ids = item_ids - item_by_id.keys()
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Item not found: {min(missing_ids)}")
    for line in payload.items:
        item = item_by_id[line.item_id]
        stock = decimal_value(item.quantity or "0", "stock quantity")
        if line.quantity > stock:
            raise HTTPException(
                status_code=409,
                detail=f"Insufficient stock for {item.name}; available: {stock}",
            )

    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        allocation = ResellerAllocations(
            reseller_id=reseller.id,
            allocated_by=user["id"],
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(allocation)
        db.flush()
        for line in payload.items:
            item = item_by_id[line.item_id]
            stock = decimal_value(item.quantity or "0", "stock quantity")
            unit_price = money(line.unit_price)
            if unit_price <= 0:
                raise HTTPException(status_code=422, detail="Unit price must be positive")
            item.quantity = str(stock - line.quantity)
            db.add(
                ResellerAllocationLines(
                    allocation_id=allocation.id,
                    item_id=item.id,
                    quantity_allocated=str(line.quantity),
                    quantity_remaining=str(line.quantity),
                    unit_price=str(unit_price),
                )
            )
            db.add(
                StockMvt(
                    item_id=item.id,
                    quantity=str(line.quantity),
                    movement_type="out",
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
        db.commit()
        return {
            "message": "Consignment allocated",
            "allocation_id": allocation.id,
        }
    except Exception:
        db.rollback()
        raise


@router.post(
    "/reseller_pg/reconcile",
    status_code=status.HTTP_201_CREATED,
    dependencies=[RESELLER_ACCESS],
)
async def reconcile_reseller(
    payload: ResellerReconciliationRequest,
    db: db_dependency,
    user: user_dependency,
):
    reseller = (
        db.query(Contact)
        .filter(
            Contact.id == payload.reseller_id,
            Contact.contact_type == "reseller",
        )
        .with_for_update()
        .first()
    )
    if reseller is None:
        raise HTTPException(status_code=404, detail="Reseller not found")
    if payload.period > datetime.now(APP_TIMEZONE).strftime("%Y-%m"):
        raise HTTPException(status_code=422, detail="Cannot reconcile a future month")
    exists = (
        db.query(ResellerReconciliations.id)
        .filter(
            ResellerReconciliations.reseller_id == reseller.id,
            ResellerReconciliations.period == payload.period,
        )
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=409,
            detail="This reseller already has a reconciliation for that month",
        )
    latest_period = (
        db.query(ResellerReconciliations.period)
        .filter(ResellerReconciliations.reseller_id == reseller.id)
        .order_by(ResellerReconciliations.period.desc())
        .limit(1)
        .scalar()
    )
    if latest_period and payload.period <= latest_period:
        raise HTTPException(
            status_code=409,
            detail=f"Reconcile a month later than {latest_period}",
        )
    allocations = (
        db.query(ResellerAllocations)
        .filter(ResellerAllocations.reseller_id == reseller.id)
        .order_by(ResellerAllocations.created_at)
        .all()
    )
    if not allocations:
        raise HTTPException(
            status_code=409,
            detail="There is no reseller-held stock to reconcile",
        )
    first_allocation_month = str(allocations[0].created_at or "")[:7]
    if first_allocation_month and payload.period < first_allocation_month:
        raise HTTPException(
            status_code=422,
            detail="The reconciliation month is before the first stock allocation",
        )
    outstanding_lines = (
        db.query(ResellerAllocationLines)
        .join(
            ResellerAllocations,
            ResellerAllocations.id == ResellerAllocationLines.allocation_id,
        )
        .filter(ResellerAllocations.reseller_id == reseller.id)
        .all()
    )
    if not any(
        decimal_value(line.quantity_remaining, "remaining quantity") > 0
        for line in outstanding_lines
    ):
        raise HTTPException(
            status_code=409,
            detail="There is no reseller-held stock to reconcile",
        )

    totals_by_line: dict[int, tuple[Decimal, Decimal]] = {}
    for line in payload.lines:
        sold, returned = totals_by_line.get(
            line.allocation_line_id,
            (Decimal("0"), Decimal("0")),
        )
        totals_by_line[line.allocation_line_id] = (
            sold + line.quantity_sold,
            returned + line.quantity_returned,
        )

    allocation_line_ids = set(totals_by_line)
    db_lines = (
        db.query(ResellerAllocationLines, ResellerAllocations)
        .join(
            ResellerAllocations,
            ResellerAllocations.id == ResellerAllocationLines.allocation_id,
        )
        .filter(
            ResellerAllocationLines.id.in_(allocation_line_ids),
            ResellerAllocations.reseller_id == reseller.id,
        )
        .with_for_update()
        .all()
        if allocation_line_ids
        else []
    )
    line_by_id = {line.id: (line, allocation) for line, allocation in db_lines}
    missing_ids = allocation_line_ids - line_by_id.keys()
    if missing_ids:
        raise HTTPException(status_code=404, detail="Consignment line not found for reseller")
    changes = []
    total_due = Decimal("0")
    for line_id, (sold, returned) in totals_by_line.items():
        allocation_line, allocation = line_by_id[line_id]
        allocation_month = str(allocation.created_at or "")[:7]
        if allocation_month and allocation_month > payload.period:
            raise HTTPException(
                status_code=422,
                detail="A reconciliation cannot include stock allocated in a later month",
            )
        remaining = decimal_value(
            allocation_line.quantity_remaining,
            "remaining consignment quantity",
        )
        if sold + returned > remaining:
            raise HTTPException(
                status_code=422,
                detail=f"Sold and returned quantities exceed the remaining quantity for line {line_id}",
            )
        unit_price = decimal_value(allocation_line.unit_price, "reseller unit price")
        amount_due = money(sold * unit_price)
        total_due += amount_due
        changes.append((allocation_line, sold, returned, unit_price, amount_due))

    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        reconciliation = ResellerReconciliations(
            reseller_id=reseller.id,
            period=payload.period,
            total_due=str(money(total_due)),
            reconciled_by=user["id"],
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(reconciliation)
        db.flush()
        for allocation_line, sold, returned, unit_price, amount_due in changes:
            allocation_line.quantity_remaining = str(
                decimal_value(
                    allocation_line.quantity_remaining,
                    "remaining consignment quantity",
                )
                - sold
                - returned
            )
            db.add(
                ResellerReconciliationLines(
                    reconciliation_id=reconciliation.id,
                    allocation_line_id=allocation_line.id,
                    quantity_sold=str(sold),
                    quantity_returned=str(returned),
                    unit_price=str(unit_price),
                    total_due=str(amount_due),
                )
            )
            if returned > 0:
                item = (
                    db.query(Item)
                    .filter(Item.id == allocation_line.item_id)
                    .with_for_update()
                    .first()
                )
                if item is None:
                    raise HTTPException(status_code=404, detail="Consigned item no longer exists")
                item.quantity = str(
                    decimal_value(item.quantity or "0", "stock quantity") + returned
                )
                db.add(
                    StockMvt(
                        item_id=item.id,
                        quantity=str(returned),
                        movement_type="in",
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                )
        db.commit()
        return {
            "message": "Monthly reconciliation recorded",
            "reconciliation_id": reconciliation.id,
            "total_due": str(money(total_due)),
        }
    except Exception:
        db.rollback()
        raise


@router.post(
    "/reseller_pg/pay",
    status_code=status.HTTP_201_CREATED,
    dependencies=[RESELLER_ACCESS],
)
async def record_reseller_payment(
    payload: ResellerPaymentRequest,
    db: db_dependency,
    user: user_dependency,
):
    reseller = (
        db.query(Contact)
        .filter(
            Contact.id == payload.reseller_id,
            Contact.contact_type == "reseller",
        )
        .with_for_update()
        .first()
    )
    if reseller is None:
        raise HTTPException(status_code=404, detail="Reseller not found")
    amount = money(payload.amount)
    balance = _balance_due(db, reseller.id)
    if amount <= 0 or amount > balance:
        raise HTTPException(
            status_code=422,
            detail=f"Payment must be positive and no more than the balance due ({format_money(balance)})",
        )
    method = validate_payment_method(payload.payment_method)
    timestamp = datetime.now(timezone.utc).isoformat()
    payment = ResellerPayments(
        reseller_id=reseller.id,
        amount=str(amount),
        payment_method=method,
        recorded_by=user["id"],
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(payment)
    db.commit()
    return {
        "message": "Reseller payment recorded",
        "balance_due": str(balance - amount),
    }
