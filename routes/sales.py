import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette import status

from database import db_dependency
from database_models import Contact, Invoices, Item, Payments, SalesTxn, StockMvt, User
from models import (
    CheckoutRequest,
    PaymentCollectionRequest,
    Role,
    SalePaymentResponse,
    SaleTransactionResponse,
)
from routes.auth import RoleChecker, get_current_user


router = APIRouter(prefix="/sales", tags=["sales"])
templates = Jinja2Templates(directory="templates")
user_dependency = Annotated[dict, Depends(get_current_user)]
APP_TIMEZONE = ZoneInfo("Africa/Harare")
CENT = Decimal("0.01")
PAYMENT_METHODS = {"cash", "card", "mobile money", "bank transfer"}
SALES_ACCESS = Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))


def _decimal(value: object, description: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {description}",
        ) from None
    if not result.is_finite():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {description}",
        )
    return result


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _compact_decimal(value: object, description: str) -> str:
    decimal_value = _decimal(value, description)
    return format(decimal_value.normalize(), ",f")


def _format_money(value: object) -> str:
    return f"MWK {_money(_decimal(value, 'money amount')):,.2f}"


templates.env.filters["money"] = _format_money


def _timestamp(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(APP_TIMEZONE).isoformat()


def _display_timestamp(value: datetime | str | None) -> str | None:
    timestamp = _timestamp(value)
    if timestamp is None:
        return None
    try:
        return datetime.fromisoformat(timestamp).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return timestamp


def _paid_total(db, invoice_id: int) -> Decimal:
    payments = (
        db.query(Payments)
        .filter(Payments.invoice_id == invoice_id, Payments.status == "completed")
        .all()
    )
    return sum((_decimal(payment.amount, "payment amount") for payment in payments), Decimal("0"))


def _invoice_status(total: Decimal, paid: Decimal) -> str:
    if paid <= 0:
        return "unpaid"
    if paid >= total:
        return "paid"
    return "partially_paid"


@router.get(
    "/",
    response_model=list[SaleTransactionResponse],
    dependencies=[SALES_ACCESS],
)
async def list_sales(db: db_dependency):
    sales = db.query(SalesTxn).order_by(SalesTxn.id.desc()).all()
    invoice_ids = {sale.invoice_id for sale in sales}
    invoices = (
        db.query(Invoices).filter(Invoices.id.in_(invoice_ids)).all()
        if invoice_ids
        else []
    )
    invoice_by_id = {invoice.id: invoice for invoice in invoices}
    payments = (
        db.query(Payments)
        .filter(Payments.invoice_id.in_(invoice_ids), Payments.status == "completed")
        .all()
        if invoice_ids
        else []
    )
    paid_by_invoice: dict[int, Decimal] = {}
    for payment in payments:
        paid_by_invoice[payment.invoice_id] = (
            paid_by_invoice.get(payment.invoice_id, Decimal("0"))
            + _decimal(payment.amount, "payment amount")
        )
    item_ids = {sale.item_id for sale in sales}
    items = db.query(Item).filter(Item.id.in_(item_ids)).all() if item_ids else []
    item_by_id = {item.id: item for item in items}

    results = []
    for sale in sales:
        invoice = invoice_by_id.get(sale.invoice_id)
        invoice_total = (
            _decimal(invoice.total_price, "invoice total")
            if invoice is not None
            else None
        )
        amount_paid = paid_by_invoice.get(sale.invoice_id, Decimal("0"))
        results.append(SaleTransactionResponse(
            id=sale.id,
            invoice_id=sale.invoice_id,
            receipt_url=f"/sales/{sale.invoice_id}/receipt",
            customer_id=invoice.customer_id if invoice is not None else None,
            invoice_status=invoice.status if invoice is not None else None,
            invoice_total=invoice_total,
            amount_paid=amount_paid,
            balance_due=(
                max(invoice_total - amount_paid, Decimal("0"))
                if invoice_total is not None
                else None
            ),
            item_id=sale.item_id,
            item_name=(
                item_by_id[sale.item_id].name
                if sale.item_id in item_by_id
                else None
            ),
            quantity=_decimal(sale.quantity, "quantity"),
            unit_price=(
                _decimal(sale.unit_price, "unit price")
                if sale.unit_price is not None
                else None
            ),
            total_price=_decimal(sale.total_price, "sale amount"),
            price_type=sale.price_type,
            payment_method=sale.payment_method,
            added_by=sale.added_by,
            location=sale.location,
            created_at=_timestamp(sale.created_at),
            updated_at=_timestamp(sale.updated_at),
        ))
    return results


@router.get(
    "/list",
    response_class=HTMLResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[SALES_ACCESS],
)
async def sales_list(request: Request, user: user_dependency, db: db_dependency):
    invoices = db.query(Invoices).order_by(Invoices.id.desc()).all()
    invoice_ids = {invoice.id for invoice in invoices}
    payments = (
        db.query(Payments)
        .filter(Payments.invoice_id.in_(invoice_ids), Payments.status == "completed")
        .all()
        if invoice_ids
        else []
    )
    paid_by_invoice: dict[int, Decimal] = {}
    for payment in payments:
        paid_by_invoice[payment.invoice_id] = (
            paid_by_invoice.get(payment.invoice_id, Decimal("0"))
            + _decimal(payment.amount, "payment amount")
        )

    customer_ids = {
        invoice.customer_id for invoice in invoices if invoice.customer_id is not None
    }
    customers = (
        db.query(Contact).filter(Contact.id.in_(customer_ids)).all()
        if customer_ids
        else []
    )
    customer_by_id = {customer.id: customer for customer in customers}
    sales = []
    for invoice in invoices:
        total = _decimal(invoice.total_price, "invoice total")
        paid = paid_by_invoice.get(invoice.id, Decimal("0"))
        customer = customer_by_id.get(invoice.customer_id)
        sales.append(
            {
                "invoice": invoice,
                "customer_name": customer.name if customer is not None else None,
                "created_at": _display_timestamp(invoice.created_at),
                "total": total,
                "paid": paid,
                "balance_due": max(total - paid, Decimal("0")),
            }
        )

    return templates.TemplateResponse(
        request,
        "sales_list.html",
        {"user": user, "sales": sales},
    )


@router.get(
    "/pos",
    response_class=HTMLResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[SALES_ACCESS],
)
async def pos_screen(request: Request, user: user_dependency, db: db_dependency):
    items = db.query(Item).order_by(Item.name).all()
    customers = (
        db.query(Contact)
        .filter(Contact.contact_type == "customer")
        .order_by(Contact.name)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "pos.html",
        {"user": user, "items": items, "customers": customers},
    )


@router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    dependencies=[SALES_ACCESS],
)
async def create_sale(
    checkout: CheckoutRequest,
    db: db_dependency,
    current_user: user_dependency,
):
    if checkout.payment_method is not None:
        checkout.payment_method = checkout.payment_method.strip().lower()
        if checkout.payment_method not in PAYMENT_METHODS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unsupported payment method",
            )

    tendered_amount = _money(checkout.amount_paid)
    if checkout.amount_paid > 0 and tendered_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Collected payment must be at least 0.01",
        )
    if tendered_amount > 0 and checkout.payment_method is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Choose a payment method when collecting payment",
        )

    quantities: dict[int, Decimal] = {}
    for line in checkout.items:
        quantities[line.item_id] = quantities.get(line.item_id, Decimal("0")) + line.quantity

    try:
        items = (
            db.query(Item)
            .filter(Item.id.in_(quantities))
            .order_by(Item.id)
            .with_for_update()
            .all()
        )
        items_by_id = {item.id: item for item in items}
        missing_ids = set(quantities) - items_by_id.keys()
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item not found: {min(missing_ids)}",
            )

        if checkout.customer_id is not None:
            customer = (
                db.query(Contact)
                .filter(
                    Contact.id == checkout.customer_id,
                    Contact.contact_type == "customer",
                )
                .first()
            )
            if customer is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found",
                )

        invoice_lines = []
        total = Decimal("0")
        for item_id, quantity in quantities.items():
            item = items_by_id[item_id]
            threshold = _decimal(
                item.wholesale_threshold or "6",
                "wholesale threshold",
            )
            if threshold <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"{item.name} has an invalid wholesale threshold",
                )
            stock = _decimal(item.quantity or "0", "stock quantity")
            if quantity > stock:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Insufficient stock for {item.name}; available: {stock}",
                )
            wholesale_quantity = threshold if quantity >= threshold else Decimal("0")
            retail_quantity = quantity - wholesale_quantity
            wholesale_unit_price = _money(
                _decimal(
                    item.selling_price_wholesale or "0",
                    "wholesale item price",
                )
            )
            retail_unit_price = _money(
                _decimal(item.selling_price_retail or "0", "retail item price")
            )
            if wholesale_quantity and wholesale_unit_price <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"{item.name} does not have a valid wholesale price",
                )
            if retail_quantity and retail_unit_price <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"{item.name} does not have a valid retail price",
                )
            line_total = _money(
                wholesale_unit_price * wholesale_quantity
                + retail_unit_price * retail_quantity
            )
            if line_total <= 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Quantity for {item.name} is too small to produce a sale amount",
                )
            unit_price = _money(line_total / quantity)
            price_type = (
                "mixed"
                if wholesale_quantity and retail_quantity
                else "wholesale"
                if wholesale_quantity
                else "retail"
            )
            total += line_total
            invoice_lines.append(
                {
                    "item_id": item.id,
                    "name": item.name,
                    "quantity": str(quantity),
                    "unit_price": str(unit_price),
                    "total": str(line_total),
                    "price_type": price_type,
                    "wholesale_quantity": str(wholesale_quantity),
                    "wholesale_unit_price": str(wholesale_unit_price),
                    "retail_quantity": str(retail_quantity),
                    "retail_unit_price": str(retail_unit_price),
                    "unit_prices": (
                        f"MWK {_compact_decimal(wholesale_unit_price, 'wholesale price')}:"
                        f"{_compact_decimal(retail_unit_price, 'retail price')}"
                    ),
                }
            )
        total = _money(total)
        amount_paid = min(tendered_amount, total)
        change_amount = tendered_amount - amount_paid

        timestamp = datetime.now(timezone.utc).isoformat()
        invoice = Invoices(
            customer_id=checkout.customer_id,
            items=json.dumps(invoice_lines),
            total_price=str(total),
            status=_invoice_status(total, amount_paid),
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(invoice)
        db.flush()

        for item_id, quantity in quantities.items():
            item = items_by_id[item_id]
            stock = _decimal(item.quantity or "0", "stock quantity")
            item.quantity = str(stock - quantity)
            db.add(
                StockMvt(
                    item_id=item_id,
                    quantity=str(quantity),
                    movement_type="out",
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
            line = next(
                invoice_line
                for invoice_line in invoice_lines
                if invoice_line["item_id"] == item_id
            )
            db.add(
                SalesTxn(
                    customer_id=checkout.customer_id,
                    invoice_id=invoice.id,
                    item_id=item_id,
                    quantity=str(quantity),
                    unit_price=line["unit_price"],
                    price_type=line["price_type"],
                    total_price=line["total"],
                    payment_method=checkout.payment_method if amount_paid else None,
                    added_by=current_user["id"],
                    location=checkout.location,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )

        if amount_paid > 0:
            db.add(
                Payments(
                    invoice_id=invoice.id,
                    amount=str(amount_paid),
                    change_amount=str(change_amount),
                    payment_method=checkout.payment_method,
                    status="completed",
                    collected_by=current_user["id"],
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )

        db.commit()
        return {
            "message": "Sale created successfully",
            "invoice_id": invoice.id,
            "total_amount": str(total),
            "tendered_amount": str(tendered_amount),
            "amount_paid": str(amount_paid),
            "change_amount": str(change_amount),
            "balance_due": str(max(total - amount_paid, Decimal("0"))),
            "receipt_url": f"/sales/{invoice.id}/receipt",
        }
    except Exception:
        db.rollback()
        raise


@router.post(
    "/pay",
    status_code=status.HTTP_201_CREATED,
    dependencies=[SALES_ACCESS],
)
async def record_payment(
    payment_request: PaymentCollectionRequest,
    db: db_dependency,
    current_user: user_dependency,
):
    method = payment_request.payment_method.strip().lower()
    if method not in PAYMENT_METHODS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported payment method",
        )

    try:
        invoice = (
            db.query(Invoices)
            .filter(Invoices.id == payment_request.invoice_id)
            .with_for_update()
            .first()
        )
        if invoice is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )
        total = _decimal(invoice.total_price, "invoice total")
        paid = _paid_total(db, invoice.id)
        balance_due = total - paid
        amount = _money(payment_request.amount)
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Payment must be at least 0.01",
            )
        if amount > balance_due:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Payment exceeds the outstanding balance of {balance_due}",
            )

        timestamp = datetime.now(timezone.utc).isoformat()
        payment = Payments(
            invoice_id=invoice.id,
            amount=str(amount),
            change_amount="0.00",
            payment_method=method,
            status="completed",
            collected_by=current_user["id"],
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(payment)
        invoice.status = _invoice_status(total, paid + amount)
        invoice.updated_at = timestamp
        db.commit()
        db.refresh(payment)
        return {
            "message": "Payment recorded successfully",
            "payment": SalePaymentResponse(
                id=payment.id,
                invoice_id=invoice.id,
                amount=amount,
                payment_method=method,
                status=payment.status,
                collected_by=payment.collected_by,
                created_at=_timestamp(payment.created_at),
            ),
            "balance_due": str(balance_due - amount),
        }
    except Exception:
        db.rollback()
        raise


@router.get(
    "/{invoice_id}/receipt",
    response_class=HTMLResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[SALES_ACCESS],
)
async def receipt(
    invoice_id: int,
    request: Request,
    user: user_dependency,
    db: db_dependency,
):
    invoice = db.query(Invoices).filter(Invoices.id == invoice_id).first()
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale receipt not found",
        )
    sales = (
        db.query(SalesTxn)
        .filter(SalesTxn.invoice_id == invoice_id)
        .order_by(SalesTxn.id)
        .all()
    )
    item_ids = {sale.item_id for sale in sales}
    items = db.query(Item).filter(Item.id.in_(item_ids)).all() if item_ids else []
    item_by_id = {item.id: item for item in items}
    payments = (
        db.query(Payments)
        .filter(Payments.invoice_id == invoice_id, Payments.status == "completed")
        .order_by(Payments.id)
        .all()
    )
    collector_ids = {payment.collected_by for payment in payments if payment.collected_by}
    collectors = (
        db.query(User).filter(User.id.in_(collector_ids)).all()
        if collector_ids
        else []
    )
    collector_by_id = {collector.id: collector for collector in collectors}
    customer = (
        db.query(Contact).filter(Contact.id == invoice.customer_id).first()
        if invoice.customer_id is not None
        else None
    )
    total = _decimal(invoice.total_price, "invoice total")
    paid = sum((_decimal(payment.amount, "payment amount") for payment in payments), Decimal("0"))
    invoice_lines = json.loads(invoice.items or "[]")
    invoice_line_by_item = {
        line["item_id"]: line for line in invoice_lines
    }
    lines = []
    for sale in sales:
        snapshot = invoice_line_by_item.get(sale.item_id, {})
        current_item = item_by_id.get(sale.item_id)
        price_segments = []
        wholesale_quantity = snapshot.get("wholesale_quantity")
        retail_quantity = snapshot.get("retail_quantity")
        if wholesale_quantity is not None and Decimal(wholesale_quantity) > 0:
            price_segments.append(
                f'{_compact_decimal(wholesale_quantity, "wholesale quantity")} @ '
                f'MWK {_compact_decimal(snapshot["wholesale_unit_price"], "wholesale price")}'
            )
        if retail_quantity is not None and Decimal(retail_quantity) > 0:
            price_segments.append(
                f'{_compact_decimal(retail_quantity, "retail quantity")} @ '
                f'MWK {_compact_decimal(snapshot["retail_unit_price"], "retail price")}'
            )
        lines.append(
            {
                "name": snapshot.get(
                    "name",
                    current_item.name if current_item is not None else "Item",
                ),
                "quantity": sale.quantity,
                "unit_prices": snapshot.get(
                    "unit_prices",
                    _compact_decimal(sale.unit_price or "0.00", "unit price"),
                ),
                "total": sale.total_price,
                "price_breakdown": (
                    "; ".join(price_segments)
                    or snapshot.get("price_type")
                    or sale.price_type
                    or "Standard price"
                ),
            }
        )
    return templates.TemplateResponse(
        request,
        "receipt.html",
        {
            "user": user,
            "invoice": invoice,
            "invoice_created_at": _display_timestamp(invoice.created_at),
            "customer": customer,
            "lines": lines,
            "payments": [
                {
                    "created_at": _display_timestamp(payment.created_at),
                    "payment_method": payment.payment_method,
                    "amount": payment.amount,
                    "change_amount": payment.change_amount or "0.00",
                    "collector": (
                        collector_by_id[payment.collected_by].name
                        if payment.collected_by in collector_by_id
                        else None
                    ),
                }
                for payment in payments
            ],
            "total": total,
            "paid": paid,
            "balance_due": max(total - paid, Decimal("0")),
            "change_amount": sum(
                (
                    _decimal(payment.change_amount or "0", "change amount")
                    for payment in payments
                ),
                Decimal("0"),
            ),
        },
    )
