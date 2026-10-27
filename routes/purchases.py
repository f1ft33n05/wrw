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
    PurchaseLines,
    Purchases,
    StockMvt,
    SupplierPayments,
)
from models import PurchaseCreateRequest, PurchasePaymentRequest, Role
from routes.auth import RoleChecker, get_current_user
from routes.ledger_utils import decimal_value, format_money, money, validate_payment_method


router = APIRouter(prefix="/purchases", tags=["purchases"])
templates = Jinja2Templates(directory="templates")
templates.env.filters["money"] = format_money
user_dependency = Annotated[dict, Depends(get_current_user)]
PURCHASE_ACCESS = Depends(RoleChecker(Role.admin, Role.manager))
APP_TIMEZONE = ZoneInfo("Africa/Harare")


def display_timestamp(value: datetime | str | None) -> str:
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


def purchase_paid(db, purchase_id: int) -> Decimal:
    payments = (
        db.query(SupplierPayments)
        .filter(SupplierPayments.purchase_id == purchase_id)
        .all()
    )
    return sum(
        (decimal_value(payment.amount, "supplier payment") for payment in payments),
        Decimal("0"),
    )


@router.get(
    "",
    response_class=HTMLResponse,
    dependencies=[PURCHASE_ACCESS],
)
@router.get(
    "/",
    response_class=HTMLResponse,
    dependencies=[PURCHASE_ACCESS],
)
async def purchase_page(request: Request, user: user_dependency, db: db_dependency):
    suppliers = (
        db.query(Contact)
        .filter(Contact.contact_type == "supplier")
        .order_by(Contact.name)
        .all()
    )
    items = db.query(Item).order_by(Item.name).all()
    purchases = db.query(Purchases).order_by(Purchases.id.desc()).all()
    purchase_ids = {purchase.id for purchase in purchases}
    purchase_lines = (
        db.query(PurchaseLines)
        .filter(PurchaseLines.purchase_id.in_(purchase_ids))
        .all()
        if purchase_ids
        else []
    )
    item_ids = {line.item_id for line in purchase_lines}
    item_by_id = {
        item.id: item
        for item in (
            db.query(Item).filter(Item.id.in_(item_ids)).all() if item_ids else []
        )
    }
    lines_by_purchase: dict[int, list[str]] = {}
    for line in purchase_lines:
        item = item_by_id.get(line.item_id)
        lines_by_purchase.setdefault(line.purchase_id, []).append(
            f"{item.name if item else 'Unknown item'} x {line.quantity} "
            f"@ {format_money(line.unit_cost)}"
        )
    payments = (
        db.query(SupplierPayments)
        .filter(SupplierPayments.purchase_id.in_(purchase_ids))
        .order_by(SupplierPayments.id)
        .all()
        if purchase_ids
        else []
    )
    paid_by_purchase: dict[int, Decimal] = {}
    for payment in payments:
        paid_by_purchase[payment.purchase_id] = (
            paid_by_purchase.get(payment.purchase_id, Decimal("0"))
            + decimal_value(payment.amount, "supplier payment")
        )
    payment_history_by_purchase: dict[int, list[dict]] = {}
    for payment in payments:
        payment_history_by_purchase.setdefault(payment.purchase_id, []).append(
            {
                "created_at": display_timestamp(payment.created_at),
                "amount": decimal_value(payment.amount, "supplier payment"),
                "payment_method": payment.payment_method,
            }
        )
    supplier_ids = {purchase.supplier_id for purchase in purchases}
    supplier_by_id = {
        contact.id: contact
        for contact in (
            db.query(Contact).filter(Contact.id.in_(supplier_ids)).all()
            if supplier_ids
            else []
        )
    }
    rows = []
    balance_by_supplier: dict[int, Decimal] = {}
    for purchase in purchases:
        total = decimal_value(purchase.total_amount, "purchase total")
        paid = paid_by_purchase.get(purchase.id, Decimal("0"))
        due = max(total - paid, Decimal("0"))
        supplier = supplier_by_id.get(purchase.supplier_id)
        rows.append(
            {
                "purchase": purchase,
                "supplier_name": supplier.name if supplier else "Unknown supplier",
                "created_at": display_timestamp(purchase.created_at),
                "line_summaries": lines_by_purchase.get(purchase.id, []),
                "payment_history": payment_history_by_purchase.get(purchase.id, []),
                "total": total,
                "paid": paid,
                "balance": due,
            }
        )
        balance_by_supplier[purchase.supplier_id] = (
            balance_by_supplier.get(purchase.supplier_id, Decimal("0")) + due
        )
    supplier_balances = [
        {
            "supplier": supplier_by_id[supplier_id],
            "balance": balance,
        }
        for supplier_id, balance in balance_by_supplier.items()
        if supplier_id in supplier_by_id
    ]
    return templates.TemplateResponse(
        request,
        "purchases.html",
        {
            "user": user,
            "suppliers": suppliers,
            "items": items,
            "purchases": rows,
            "supplier_balances": supplier_balances,
            "display_timestamp": display_timestamp,
        },
    )


@router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    dependencies=[PURCHASE_ACCESS],
)
async def create_purchase(
    payload: PurchaseCreateRequest,
    db: db_dependency,
    user: user_dependency,
):
    supplier = (
        db.query(Contact)
        .filter(
            Contact.id == payload.supplier_id,
            Contact.contact_type == "supplier",
        )
        .first()
    )
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")

    quantities: dict[int, Decimal] = {}
    for line in payload.items:
        quantities[line.item_id] = quantities.get(line.item_id, Decimal("0")) + line.quantity
    items = (
        db.query(Item)
        .filter(Item.id.in_(quantities))
        .order_by(Item.id)
        .with_for_update()
        .all()
    )
    item_by_id = {item.id: item for item in items}
    missing_ids = set(quantities) - item_by_id.keys()
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Item not found: {min(missing_ids)}")

    lines = []
    total = Decimal("0")
    for request_line in payload.items:
        unit_cost = money(request_line.unit_cost)
        line_total = money(request_line.quantity * unit_cost)
        total += line_total
        lines.append(
            {
                "item_id": request_line.item_id,
                "quantity": request_line.quantity,
                "unit_cost": unit_cost,
                "total": line_total,
            }
        )
    total = money(total)
    amount_paid = money(payload.amount_paid)
    if amount_paid > total:
        raise HTTPException(
            status_code=422,
            detail="Supplier payment cannot exceed the purchase total",
        )
    payment_method = None
    if amount_paid > 0:
        if not payload.payment_method:
            raise HTTPException(status_code=422, detail="Choose a payment method")
        payment_method = validate_payment_method(payload.payment_method)

    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        purchase = Purchases(
            supplier_id=supplier.id,
            total_amount=str(total),
            created_by=user["id"],
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(purchase)
        db.flush()
        for line in lines:
            item = item_by_id[line["item_id"]]
            stock = decimal_value(item.quantity or "0", "stock quantity")
            quantity = line["quantity"]
            item.quantity = str(stock + quantity)
            db.add(
                PurchaseLines(
                    purchase_id=purchase.id,
                    item_id=item.id,
                    quantity=str(quantity),
                    unit_cost=str(line["unit_cost"]),
                    total_amount=str(line["total"]),
                )
            )
            db.add(
                StockMvt(
                    item_id=item.id,
                    quantity=str(quantity),
                    movement_type="in",
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
        if amount_paid > 0:
            db.add(
                SupplierPayments(
                    purchase_id=purchase.id,
                    amount=str(amount_paid),
                    payment_method=payment_method,
                    recorded_by=user["id"],
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
        db.commit()
        return {
            "message": "Purchase received",
            "purchase_id": purchase.id,
            "total": str(total),
            "paid": str(amount_paid),
            "balance_due": str(total - amount_paid),
        }
    except Exception:
        db.rollback()
        raise


@router.post(
    "/pay",
    status_code=status.HTTP_201_CREATED,
    dependencies=[PURCHASE_ACCESS],
)
async def record_supplier_payment(
    payload: PurchasePaymentRequest,
    db: db_dependency,
    user: user_dependency,
):
    purchase = (
        db.query(Purchases)
        .filter(Purchases.id == payload.purchase_id)
        .with_for_update()
        .first()
    )
    if purchase is None:
        raise HTTPException(status_code=404, detail="Purchase not found")
    amount = money(payload.amount)
    balance = max(
        decimal_value(purchase.total_amount, "purchase total")
        - purchase_paid(db, purchase.id),
        Decimal("0"),
    )
    if amount <= 0 or amount > balance:
        raise HTTPException(
            status_code=422,
            detail=f"Payment must be positive and no more than the balance due ({format_money(balance)})",
        )
    method = validate_payment_method(payload.payment_method)
    timestamp = datetime.now(timezone.utc).isoformat()
    payment = SupplierPayments(
        purchase_id=purchase.id,
        amount=str(amount),
        payment_method=method,
        recorded_by=user["id"],
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(payment)
    db.commit()
    return {
        "message": "Supplier payment recorded",
        "balance_due": str(balance - amount),
    }
