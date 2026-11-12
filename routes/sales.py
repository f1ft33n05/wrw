import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette import status

from database import db_dependency
from database_models import (
    Contact,
    EventStockAllocation,
    Events,
    Invoices,
    Item,
    ItemCategory,
    ItemDiscount,
    Payments,
    SalesReturnLines,
    SalesReturns,
    SalesTxn,
    StockMvt,
    User,
)
from models import (
    CheckoutRequest,
    PaymentCollectionRequest,
    Role,
    SaleReturnRequest,
    SalePaymentResponse,
    SaleTransactionResponse,
)
from routes.auth import RoleChecker, get_current_user
from config import APP_TIMEZONE as CONFIGURED_TIMEZONE
from config import CURRENCY_CODE
from idempotency import get_cached_response, require_idempotency_key, save_response
from event_stock import return_expired_event_stock


router = APIRouter(prefix="/sales", tags=["sales"])
templates = Jinja2Templates(directory="templates")
user_dependency = Annotated[dict, Depends(get_current_user)]
APP_TIMEZONE = CONFIGURED_TIMEZONE
CENT = Decimal("0.01")
PAYMENT_METHODS = {"cash", "card", "mobile money", "bank transfer"}


def _event_starts_on(value: object, target_date) -> bool:
    if not value:
        return False
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date() == target_date
    except ValueError:
        return str(value).split("T", 1)[0] == target_date.isoformat()
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
    return f"{CURRENCY_CODE} {_money(_decimal(value, 'money amount')):,.2f}"


def _active_discount(db, item: Item) -> Decimal:
    discounts = db.query(ItemDiscount).filter(ItemDiscount.active == 1).all()
    item_discount = next((d for d in discounts if d.discount_type == "item" and d.target_id == item.id), None)
    category_discount = next((d for d in discounts if d.discount_type == "category" and d.target_id == item.category_id), None)
    discount = item_discount or category_discount
    return _decimal(discount.percentage, "discount percentage") if discount else Decimal("0")


def _active_customer_discount(db, customer_id: int | None) -> Decimal:
    if customer_id is None:
        return Decimal("0")
    discount = (
        db.query(ItemDiscount)
        .filter(
            ItemDiscount.discount_type == "customer",
            ItemDiscount.target_id == customer_id,
            ItemDiscount.active == 1,
        )
        .order_by(ItemDiscount.id)
        .first()
    )
    return _decimal(discount.percentage, "customer discount") if discount else Decimal("0")


def is_pos_draft_invoice(invoice: Invoices) -> bool:
    try:
        lines = json.loads(invoice.items or "[]")
    except (TypeError, ValueError):
        return False
    if not isinstance(lines, list) or not lines:
        return False
    valid_sale_lines = all(
        isinstance(line, dict) and "item_id" in line and "quantity" in line
        for line in lines
    )
    return valid_sale_lines and (
        invoice.document_number is None
        or all("price_type" in line for line in lines)
    )


def _allocate_discount_to_lines(
    invoice_lines: list[dict],
    subtotal: Decimal,
    discount_amount: Decimal,
) -> None:
    remaining_discount = discount_amount
    for index, line in enumerate(invoice_lines):
        line_subtotal = _decimal(line["subtotal"], "invoice line subtotal")
        if index == len(invoice_lines) - 1:
            line_discount = remaining_discount
        else:
            line_discount = _money(discount_amount * line_subtotal / subtotal)
            line_discount = min(line_discount, remaining_discount, line_subtotal)
        remaining_discount -= line_discount
        line_total = _money(line_subtotal - line_discount)
        quantity = _decimal(line["quantity"], "invoice line quantity")
        line["discount_amount"] = str(line_discount)
        line["discount_percentage"] = str(
            _money(line_discount * Decimal("100") / line_subtotal)
        )
        line["total"] = str(line_total)
        line["unit_price"] = str(_money(line_total / quantity))


templates.env.filters["money"] = _format_money


def _format_plain_money(value: object) -> str:
    return f"{_money(_decimal(value, 'money amount')):,.2f}"


templates.env.filters["plain_money"] = _format_plain_money


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


def _returned_totals(db, sale_txn_ids: set[int]) -> dict[int, tuple[Decimal, Decimal]]:
    if not sale_txn_ids:
        return {}
    totals: dict[int, tuple[Decimal, Decimal]] = {}
    return_lines = (
        db.query(SalesReturnLines)
        .filter(SalesReturnLines.sale_txn_id.in_(sale_txn_ids))
        .all()
    )
    for line in return_lines:
        quantity, amount = totals.get(line.sale_txn_id, (Decimal("0"), Decimal("0")))
        totals[line.sale_txn_id] = (
            quantity + _decimal(line.quantity, "returned quantity"),
            amount + _decimal(line.refund_amount, "refund amount"),
        )
    return totals


def _returnable_lines(db, invoice: Invoices) -> list[dict]:
    sale_lines = (
        db.query(SalesTxn)
        .filter(SalesTxn.invoice_id == invoice.id)
        .order_by(SalesTxn.id)
        .all()
    )
    returned_totals = _returned_totals(db, {line.id for line in sale_lines})
    item_ids = {line.item_id for line in sale_lines}
    item_names = {
        item.id: item.name
        for item in (db.query(Item).filter(Item.id.in_(item_ids)).all() if item_ids else [])
    }
    results = []
    for sale_line in sale_lines:
        sold_quantity = _decimal(sale_line.quantity, "sold quantity")
        sold_total = _decimal(sale_line.total_price, "sale line total")
        returned_quantity, returned_amount = returned_totals.get(
            sale_line.id, (Decimal("0"), Decimal("0"))
        )
        results.append({
            "sale_txn_id": sale_line.id,
            "item_name": item_names.get(sale_line.item_id, f"Item {sale_line.item_id}"),
            "sold_quantity": sold_quantity,
            "returned_quantity": returned_quantity,
            "remaining_quantity": max(sold_quantity - returned_quantity, Decimal("0")),
            "remaining_refund": max(sold_total - returned_amount, Decimal("0")),
            "event_id": sale_line.event_id,
        })
    return results


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
    items = db.query(Item).order_by(Item.name).all()
    customers = (
        db.query(Contact)
        .filter(Contact.contact_type == "customer")
        .order_by(Contact.name)
        .all()
    )
    events = (
        db.query(Events)
        .filter(Events.status.in_(["planned", "active"]))
        .order_by(Events.starts_at.desc(), Events.name)
        .all()
    )
    event_ids = {invoice.event_id for invoice in invoices if invoice.event_id is not None}
    events = (
        db.query(Events).filter(Events.id.in_(event_ids)).all()
        if event_ids
        else []
    )
    event_by_id = {event.id: event for event in events}
    invoice_ids = {invoice.id for invoice in invoices}
    payments = (
        db.query(Payments)
        .filter(Payments.invoice_id.in_(invoice_ids), Payments.status == "completed")
        .all()
        if invoice_ids
        else []
    )
    paid_by_invoice: dict[int, Decimal] = {}
    payment_methods_by_invoice: dict[int, set[str]] = {}
    for payment in payments:
        paid_by_invoice[payment.invoice_id] = (
            paid_by_invoice.get(payment.invoice_id, Decimal("0"))
            + _decimal(payment.amount, "payment amount")
        )
        if payment.payment_method:
            payment_methods_by_invoice.setdefault(payment.invoice_id, set()).add(
                payment.payment_method.strip().lower()
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
                "customer_id": str(invoice.customer_id) if invoice.customer_id is not None else "walk-in",
                "customer_name": customer.name if customer is not None else None,
                "event_id": str(invoice.event_id) if invoice.event_id is not None else "store",
                "event_name": event_by_id[invoice.event_id].name if invoice.event_id in event_by_id else None,
                "created_at": _display_timestamp(invoice.created_at),
                "created_at_iso": _timestamp(invoice.created_at),
                "total": total,
                "paid": paid,
                "balance_due": max(total - paid, Decimal("0")),
                "payment_methods": sorted(payment_methods_by_invoice.get(invoice.id, set())),
            }
        )
    sales_totals = {
        "total": sum((sale["total"] for sale in sales), Decimal("0")),
        "paid": sum((sale["paid"] for sale in sales), Decimal("0")),
        "balance_due": sum((sale["balance_due"] for sale in sales), Decimal("0")),
    }
    payment_methods = sorted(
        {
            method
            for sale in sales
            for method in sale["payment_methods"]
        }
    )
    customer_options = sorted(
        {
            (sale["customer_id"], sale["customer_name"] or "Walk-in customer")
            for sale in sales
        },
        key=lambda customer: customer[1].casefold(),
    )
    status_options = sorted(
        {
            sale["invoice"].status.lower()
            for sale in sales
            if sale["invoice"].status
        }
    )

    return templates.TemplateResponse(
        request,
        "sales_list.html",
        {
            "user": user,
            "sales": sales,
            "sales_totals": sales_totals,
            "payment_methods": payment_methods,
            "customer_options": customer_options,
            "status_options": status_options,
            "currency": CURRENCY_CODE,
            "items": items,
            "customers": customers,
            "events": events,
            "selected_event_id": None,
        },
    )


@router.get("/receipts", response_class=HTMLResponse, dependencies=[SALES_ACCESS])
async def sales_receipts(request: Request, user: user_dependency, db: db_dependency):
    invoices = db.query(Invoices).order_by(Invoices.created_at.desc()).all()
    customer_ids = {invoice.customer_id for invoice in invoices if invoice.customer_id}
    customers = {
        contact.id: contact.name
        for contact in (
            db.query(Contact).filter(Contact.id.in_(customer_ids)).all()
            if customer_ids else []
        )
    }
    rows = []
    for invoice in invoices:
        if invoice.created_at is not None:
            rows.append({
                "id": invoice.id,
                "document_number": invoice.document_number or f"INV-{invoice.id}",
                "customer": customers.get(invoice.customer_id, "Walk-in customer"),
                "created_at": _display_timestamp(invoice.created_at),
                "total": _decimal(invoice.total_price, "invoice total"),
                "receipt_url": f"/sales/{invoice.id}/receipt",
            })
    return templates.TemplateResponse(request, "sales_receipts.html", {
        "user": user,
        "receipts": rows,
    })


@router.get("/payments", response_class=HTMLResponse, dependencies=[SALES_ACCESS])
async def sales_payments(request: Request, user: user_dependency, db: db_dependency):
    payments = db.query(Payments).filter(Payments.status == "completed").order_by(Payments.created_at.desc()).all()
    invoice_ids = {payment.invoice_id for payment in payments if payment.invoice_id}
    invoices = {
        invoice.id: invoice
        for invoice in (
            db.query(Invoices).filter(Invoices.id.in_(invoice_ids)).all()
            if invoice_ids else []
        )
    }
    customer_ids = {
        invoice.customer_id for invoice in invoices.values() if invoice.customer_id
    }
    customers = {
        contact.id: contact.name
        for contact in (
            db.query(Contact).filter(Contact.id.in_(customer_ids)).all()
            if customer_ids else []
        )
    }
    collector_ids = {payment.collected_by for payment in payments if payment.collected_by}
    collectors = {
        collector.id: collector.name
        for collector in (
            db.query(User).filter(User.id.in_(collector_ids)).all()
            if collector_ids else []
        )
    }
    rows = []
    for payment in payments:
        invoice = invoices.get(payment.invoice_id)
        rows.append({
            "id": payment.id,
            "invoice_number": invoice.document_number if invoice and invoice.document_number else f"INV-{payment.invoice_id}",
            "customer": customers.get(invoice.customer_id, "Walk-in customer") if invoice else "Walk-in customer",
            "amount": _decimal(payment.amount, "payment amount"),
            "payment_method": payment.payment_method,
            "collected_by": collectors.get(payment.collected_by, "-"),
            "created_at": _display_timestamp(payment.created_at),
            "receipt_url": f"/sales/{payment.invoice_id}/receipt",
        })
    return templates.TemplateResponse(request, "sales_payments.html", {
        "user": user,
        "payments": rows,
    })


@router.get("/returns", response_class=HTMLResponse, dependencies=[SALES_ACCESS])
async def sales_returns_page(
    request: Request,
    user: user_dependency,
    db: db_dependency,
    invoice_id: int | None = None,
):
    invoices = (
        db.query(Invoices)
        .join(SalesTxn, SalesTxn.invoice_id == Invoices.id)
        .filter(Invoices.status != "draft")
        .order_by(Invoices.created_at.desc(), Invoices.id.desc())
        .distinct()
        .limit(100)
        .all()
    )
    selected_invoice = None
    lines = []
    if invoice_id is not None:
        selected_invoice = (
            db.query(Invoices)
            .filter(Invoices.id == invoice_id, Invoices.status != "draft")
            .first()
        )
        if selected_invoice is None:
            raise HTTPException(status_code=404, detail="Sale not found")
        lines = _returnable_lines(db, selected_invoice)
        if not lines:
            raise HTTPException(status_code=404, detail="Sale has no returnable items")
    return templates.TemplateResponse(request, "sales_returns.html", {
        "user": user,
        "invoices": invoices,
        "selected_invoice": selected_invoice,
        "lines": lines,
    })


@router.post(
    "/returns",
    status_code=status.HTTP_201_CREATED,
    dependencies=[SALES_ACCESS],
)
async def create_sale_return(
    payload: SaleReturnRequest,
    db: db_dependency,
    current_user: user_dependency,
    request: Request,
):
    require_idempotency_key(request)
    cached = get_cached_response(db, request)
    if cached:
        return JSONResponse(status_code=cached[0], content=cached[1])

    return_expired_event_stock(db)
    try:
        invoice = (
            db.query(Invoices)
            .filter(Invoices.id == payload.invoice_id, Invoices.status != "draft")
            .with_for_update()
            .first()
        )
        if invoice is None:
            raise HTTPException(status_code=404, detail="Sale not found")

        sale_lines = (
            db.query(SalesTxn)
            .filter(SalesTxn.invoice_id == invoice.id)
            .with_for_update()
            .all()
        )
        sale_lines_by_id = {line.id: line for line in sale_lines}
        requested_ids = {line.sale_txn_id for line in payload.items}
        if not requested_ids.issubset(sale_lines_by_id):
            raise HTTPException(status_code=422, detail="A selected item does not belong to this sale")

        already_returned = _returned_totals(db, set(sale_lines_by_id))
        existing_returns = (
            db.query(SalesReturns)
            .filter(SalesReturns.invoice_id == invoice.id)
            .with_for_update()
            .all()
        )
        previously_refunded = sum(
            (_decimal(record.total_refund, "previous refund") for record in existing_returns),
            Decimal("0"),
        )
        refund_lines = []
        total_refund = Decimal("0")
        for requested_line in payload.items:
            sale_line = sale_lines_by_id[requested_line.sale_txn_id]
            sold_quantity = _decimal(sale_line.quantity, "sold quantity")
            sold_total = _decimal(sale_line.total_price, "sale line total")
            returned_quantity, refunded_amount = already_returned.get(
                sale_line.id, (Decimal("0"), Decimal("0"))
            )
            remaining_quantity = sold_quantity - returned_quantity
            remaining_amount = sold_total - refunded_amount
            if requested_line.quantity > remaining_quantity:
                raise HTTPException(
                    status_code=409,
                    detail=f"Return quantity exceeds the remaining quantity for item {sale_line.item_id}",
                )
            refund_amount = (
                remaining_amount
                if requested_line.quantity == remaining_quantity
                else _money(remaining_amount * requested_line.quantity / remaining_quantity)
            )
            if refund_amount <= 0:
                raise HTTPException(status_code=409, detail="This sale line has no refundable amount remaining")
            refund_lines.append((sale_line, requested_line.quantity, refund_amount))
            total_refund += refund_amount

        paid_total = _paid_total(db, invoice.id)
        if total_refund + previously_refunded > paid_total:
            raise HTTPException(
                status_code=409,
                detail="Refund exceeds the amount collected for this sale",
            )

        timestamp = datetime.now(timezone.utc).isoformat()
        return_record = SalesReturns(
            invoice_id=invoice.id,
            refund_method=payload.refund_method,
            total_refund=str(_money(total_refund)),
            processed_by=current_user["id"],
            created_at=timestamp,
        )
        db.add(return_record)
        db.flush()

        for sale_line, quantity, refund_amount in refund_lines:
            item = db.query(Item).filter(Item.id == sale_line.item_id).with_for_update().first()
            if item is None:
                raise HTTPException(status_code=409, detail=f"Item {sale_line.item_id} no longer exists")

            if sale_line.event_id is not None:
                event = (
                    db.query(Events)
                    .filter(Events.id == sale_line.event_id)
                    .with_for_update()
                    .first()
                )
                allocation = (
                    db.query(EventStockAllocation)
                    .filter(
                        EventStockAllocation.event_id == sale_line.event_id,
                        EventStockAllocation.item_id == sale_line.item_id,
                    )
                    .with_for_update()
                    .first()
                )
                if event is None or allocation is None:
                    raise HTTPException(
                        status_code=409,
                        detail="The original event stock allocation is unavailable",
                    )
                if event.status in {"closed", "cancelled", "archived"} or allocation.status == "returned":
                    item.quantity = str(_decimal(item.quantity or "0", "item stock") + quantity)
                else:
                    allocation.quantity_remaining = str(
                        _decimal(allocation.quantity_remaining, "event stock")
                        + quantity
                    )
                    allocation.status = "active"
                    allocation.updated_at = timestamp
            else:
                item.quantity = str(_decimal(item.quantity or "0", "item stock") + quantity)

            item.updated_at = timestamp
            db.add(StockMvt(
                item_id=item.id,
                quantity=str(quantity),
                movement_type="in",
                note=f"Sale return #{invoice.id}",
                created_at=timestamp,
                updated_at=timestamp,
            ))
            db.add(SalesReturnLines(
                return_id=return_record.id,
                sale_txn_id=sale_line.id,
                item_id=sale_line.item_id,
                quantity=str(quantity),
                refund_amount=str(refund_amount),
            ))

        response = {
            "message": "Sale return processed",
            "return_id": return_record.id,
            "invoice_id": invoice.id,
            "refund_amount": str(_money(total_refund)),
            "refund_method": payload.refund_method,
        }
        save_response(db, request, status.HTTP_201_CREATED, response)
        db.commit()
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=response)
    except Exception:
        db.rollback()
        raise


@router.get(
    "/pos",
    response_class=HTMLResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[SALES_ACCESS],
)
async def pos_screen(
    request: Request,
    user: user_dependency,
    db: db_dependency,
    event_id: int | None = None,
    resume_draft_id: int | None = None,
):
    return_expired_event_stock(db)
    resume_draft = None
    if resume_draft_id is not None:
        resume_draft = (
            db.query(Invoices)
            .filter(
                Invoices.id == resume_draft_id,
                Invoices.created_by == user["id"],
                Invoices.status == "draft",
            )
            .first()
        )
        if resume_draft is None or not is_pos_draft_invoice(resume_draft):
            raise HTTPException(status_code=404, detail="Paused POS sale not found")
        if event_id is not None and event_id != resume_draft.event_id:
            raise HTTPException(status_code=409, detail="Paused sale belongs to a different event")
        event_id = resume_draft.event_id

    catalog_items = db.query(Item).order_by(Item.name).all()
    items = catalog_items
    categories = db.query(ItemCategory).order_by(ItemCategory.name).all()
    active_discounts = (
        db.query(ItemDiscount)
        .filter(ItemDiscount.active == 1)
        .order_by(ItemDiscount.id)
        .all()
    )
    discount_by_target: dict[tuple[str, int], Decimal] = {}
    for discount in active_discounts:
        discount_by_target.setdefault(
            (discount.discount_type, discount.target_id),
            _decimal(discount.percentage, "discount percentage"),
        )
    item_discount_percentages = {
        item.id: str(
            discount_by_target.get(
                ("item", item.id),
                discount_by_target.get(("category", item.category_id), Decimal("0")),
            )
        )
        for item in items
    }
    customer_discount_percentages = {
        target_id: str(percentage)
        for (discount_type, target_id), percentage in discount_by_target.items()
        if discount_type == "customer"
    }
    if event_id is None:
        items = [
            {**{column.name: getattr(item, column.name) for column in Item.__table__.columns}, "quantity": str(item.quantity or "0")}
            for item in items
            if _decimal(item.quantity or "0", "stock quantity") > 0
        ]
    else:
        allocations = db.query(EventStockAllocation).filter(
            EventStockAllocation.event_id == event_id,
            EventStockAllocation.status == "active",
            EventStockAllocation.quantity_remaining != "0",
        ).all()
        allocation_by_item = {allocation.item_id: _decimal(allocation.quantity_remaining, "remaining quantity") for allocation in allocations}
        items = [
            {**{column.name: getattr(item, column.name) for column in Item.__table__.columns}, "quantity": str(allocation_by_item[item.id])}
            for item in items
            if item.id in allocation_by_item
        ]
    if resume_draft is not None:
        draft_item_ids = {
            line.get("item_id")
            for line in json.loads(resume_draft.items or "[]")
            if isinstance(line, dict)
        }
        displayed_item_ids = {item["id"] for item in items}
        for item in catalog_items:
            if item.id in draft_item_ids and item.id not in displayed_item_ids:
                items.append({
                    **{column.name: getattr(item, column.name) for column in Item.__table__.columns},
                    "quantity": str(item.quantity or "0") if event_id is None else "0",
                })
    customers = (
        db.query(Contact)
        .filter(Contact.contact_type == "customer")
        .order_by(Contact.name)
        .all()
    )
    events = (
        db.query(Events)
        .filter(Events.status.in_(["planned", "active"]))
        .order_by(Events.starts_at.desc(), Events.name)
        .all()
    )
    draft_invoices = (
        db.query(Invoices)
        .filter(
            Invoices.status == "draft",
            Invoices.created_by == user["id"],
        )
        .order_by(Invoices.id.desc())
        .all()
    )
    drafts = [
        {
            "id": invoice.id,
            "line_items": json.loads(invoice.items or "[]"),
            "total": _decimal(invoice.total_price, "draft total"),
            "customer_id": invoice.customer_id,
            "event_id": invoice.event_id,
            "created_at": _display_timestamp(invoice.created_at),
        }
        for invoice in draft_invoices
        if is_pos_draft_invoice(invoice)
    ]
    if event_id is not None:
        selected_event = db.query(Events).filter(Events.id == event_id).first()
        if selected_event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        if not _event_starts_on(selected_event.starts_at, datetime.now(APP_TIMEZONE).date()):
            raise HTTPException(status_code=409, detail="Event POS opens on the event start date")
    else:
        selected_event = None
    recent_invoices = (
        db.query(Invoices)
        .join(SalesTxn, SalesTxn.invoice_id == Invoices.id)
        .filter(Invoices.status != "draft")
        .order_by(Invoices.created_at.desc(), Invoices.id.desc())
        .distinct()
        .limit(10)
        .all()
    )
    recent_customer_ids = {
        invoice.customer_id
        for invoice in recent_invoices
        if invoice.customer_id is not None
    }
    recent_customers = {
        customer.id: customer.name
        for customer in (
            db.query(Contact).filter(Contact.id.in_(recent_customer_ids)).all()
            if recent_customer_ids
            else []
        )
    }
    recent_transactions = [
        {
            "id": invoice.id,
            "customer": recent_customers.get(invoice.customer_id, "Walk-in customer"),
            "created_at": _display_timestamp(invoice.created_at),
            "total": _decimal(invoice.total_price, "invoice total"),
            "status": invoice.status,
        }
        for invoice in recent_invoices
    ]
    return templates.TemplateResponse(
        request,
        "pos.html",
        {
            "user": user,
            "items": items,
            "categories": categories,
            "item_discount_percentages": item_discount_percentages,
            "customer_discount_percentages": customer_discount_percentages,
            "customers": customers,
            "events": events,
            "drafts": drafts,
            "resume_draft_id": resume_draft.id if resume_draft is not None else None,
            "recent_transactions": recent_transactions,
            "selected_event_id": event_id,
            "selected_event": selected_event,
        },
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
    request: Request,
):
    require_idempotency_key(request)
    cached = get_cached_response(db, request)
    if cached:
        return JSONResponse(status_code=cached[0], content=cached[1])
    event = None
    if checkout.event_id is not None:
        event = db.query(Events).filter(Events.id == checkout.event_id).with_for_update().first()
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        if event.status not in {"planned", "active"}:
            raise HTTPException(status_code=409, detail="Sales cannot be closed for this event")
        if not _event_starts_on(event.starts_at, datetime.now(APP_TIMEZONE).date()):
            raise HTTPException(status_code=409, detail="Sales can only be created on the event start date")
        checkout.location = f"Event: {event.name}"

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

        customer_discount = _active_customer_discount(db, checkout.customer_id)
        invoice_lines = []
        subtotal = Decimal("0")
        for item_id, quantity in quantities.items():
            item = items_by_id[item_id]
            stock = _decimal(item.quantity or "0", "stock quantity")
            if checkout.event_id is not None:
                allocation = db.query(EventStockAllocation).filter(
                    EventStockAllocation.event_id == checkout.event_id,
                    EventStockAllocation.item_id == item_id,
                    EventStockAllocation.status == "active",
                ).with_for_update().first()
                if allocation is None:
                    raise HTTPException(status_code=409, detail=f"{item.name} is not assigned to this event")
                available = _decimal(allocation.quantity_remaining, "remaining event stock")
            else:
                available = stock
            if quantity > available:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Insufficient available stock for {item.name}; available: {available}",
                )
            threshold = _decimal(
                item.wholesale_threshold or "6",
                "wholesale threshold",
            )
            if threshold <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"{item.name} has an invalid wholesale threshold",
                )
            wholesale_quantity = (quantity // threshold) * threshold
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
            discount_percentage = _active_discount(db, item)
            undiscounted_total = _money(
                wholesale_unit_price * wholesale_quantity
                + retail_unit_price * retail_quantity
            )
            discount_amount = _money(undiscounted_total * discount_percentage / Decimal("100"))
            line_total = _money(undiscounted_total - discount_amount)
            unit_price = _money(line_total / quantity)
            price_type = (
                "mixed"
                if wholesale_quantity and retail_quantity
                else "wholesale"
                if wholesale_quantity
                else "retail"
            )
            subtotal += undiscounted_total
            invoice_lines.append(
                {
                    "item_id": item.id,
                    "name": item.name,
                    "description": item.name,
                    "quantity": str(quantity),
                    "unit_price": str(unit_price),
                    "total": str(line_total),
                    "subtotal": str(undiscounted_total),
                    "discount_percentage": str(discount_percentage),
                    "discount_amount": str(discount_amount),
                    "price_type": price_type,
                    "wholesale_quantity": str(wholesale_quantity),
                    "wholesale_unit_price": str(wholesale_unit_price),
                    "retail_quantity": str(retail_quantity),
                    "retail_unit_price": str(retail_unit_price),
                    "unit_prices": (
                        f"{_compact_decimal(wholesale_unit_price, 'wholesale price')}:"
                        f"{_compact_decimal(retail_unit_price, 'retail price')}"
                    ),
                }
            )
        subtotal = _money(subtotal)
        customer_discount_applies = (
            checkout.discount_mode == "automatic" and customer_discount > 0
        )
        sale_discount_applies = (
            checkout.discount_mode != "automatic" or customer_discount_applies
        )
        if sale_discount_applies:
            if checkout.discount_mode == "percentage":
                sale_discount_amount = _money(
                    subtotal * checkout.discount_value / Decimal("100")
                )
            elif checkout.discount_mode == "amount":
                if checkout.discount_value > subtotal:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Discount cannot exceed the sale subtotal",
                    )
                sale_discount_amount = _money(checkout.discount_value)
            else:
                sale_discount_amount = _money(
                    subtotal * customer_discount / Decimal("100")
                )
            _allocate_discount_to_lines(
                invoice_lines,
                subtotal,
                sale_discount_amount,
            )
            total_discount = sale_discount_amount
            total = _money(subtotal - total_discount)
        else:
            if any(
                _decimal(line["total"], "invoice line total") <= 0
                for line in invoice_lines
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="A discount cannot reduce an item total to zero",
                )
            total = _money(
                sum(
                    (_decimal(line["total"], "invoice line total") for line in invoice_lines),
                    Decimal("0"),
                )
            )
            total_discount = _money(
                sum(
                    (_decimal(line["discount_amount"], "line discount amount") for line in invoice_lines),
                    Decimal("0"),
                )
            )
        if total <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Discount cannot reduce the sale total to zero",
            )
        for line in invoice_lines:
            line["sale_discount_mode"] = checkout.discount_mode
            line["sale_discount_value"] = (
                str(checkout.discount_value)
                if checkout.discount_value is not None
                else None
            )
        amount_paid = min(tendered_amount, total)
        change_amount = tendered_amount - amount_paid

        timestamp = datetime.now(timezone.utc).isoformat()
        invoice = Invoices(
            customer_id=checkout.customer_id,
            event_id=checkout.event_id,
            created_by=current_user["id"],
            items=json.dumps(invoice_lines),
            subtotal=str(subtotal),
            discount_amount=str(total_discount),
            total_price=str(total),
            status="draft" if checkout.save_draft else _invoice_status(total, amount_paid),
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(invoice)
        db.flush()

        if not checkout.save_draft:
            for item_id, quantity in quantities.items():
                item = items_by_id[item_id]
                stock = _decimal(item.quantity or "0", "stock quantity")
                if checkout.event_id is not None:
                    allocation = db.query(EventStockAllocation).filter(
                        EventStockAllocation.event_id == checkout.event_id,
                        EventStockAllocation.item_id == item_id,
                        EventStockAllocation.status == "active",
                    ).with_for_update().first()
                    if allocation is not None:
                        allocation.quantity_remaining = str(
                            _decimal(allocation.quantity_remaining, "remaining event stock") - quantity
                        )
                        if Decimal(allocation.quantity_remaining) == 0:
                            allocation.status = "sold"
                        allocation.updated_at = timestamp
                else:
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
                        event_id=checkout.event_id,
                        invoice_id=invoice.id,
                    item_id=item_id,
                    quantity=str(quantity),
                        unit_price=line["unit_price"],
                        price_type=line["price_type"],
                        total_price=line["total"],
                        discount_percentage=line["discount_percentage"],
                        discount_amount=line["discount_amount"],
                        payment_method=checkout.payment_method if amount_paid else None,
                        added_by=current_user["id"],
                        location=checkout.location,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )

        if amount_paid > 0 and not checkout.save_draft:
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
        response = {
            "message": "Sale created successfully",
            "invoice_id": invoice.id,
            "total_amount": str(total),
            "tendered_amount": str(tendered_amount),
            "amount_paid": str(amount_paid),
            "change_amount": str(change_amount),
            "balance_due": str(max(total - amount_paid, Decimal("0"))),
            "receipt_url": f"/sales/{invoice.id}/receipt",
        }
        save_response(db, request, status.HTTP_201_CREATED, response)
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


@router.delete(
    "/draft/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[SALES_ACCESS],
)
async def delete_draft(
    invoice_id: int,
    db: db_dependency,
    current_user: user_dependency,
):
    invoice = (
        db.query(Invoices)
        .filter(
            Invoices.id == invoice_id,
            Invoices.status == "draft",
            Invoices.created_by == current_user["id"],
        )
        .first()
    )
    if invoice is None or not is_pos_draft_invoice(invoice):
        raise HTTPException(status_code=404, detail="Draft sale not found")
    db.delete(invoice)
    db.commit()


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
    event = (
        db.query(Events).filter(Events.id == invoice.event_id).first()
        if invoice.event_id is not None
        else None
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
    cashier_id = invoice.created_by or next(
        (payment.collected_by for payment in payments if payment.collected_by),
        None,
    )
    cashier = db.query(User).filter(User.id == cashier_id).first() if cashier_id else None
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
        unit_prices = []
        wholesale_quantity = _decimal(
            snapshot.get("wholesale_quantity", "0"),
            "wholesale quantity",
        )
        retail_quantity = _decimal(
            snapshot.get("retail_quantity", "0"),
            "retail quantity",
        )
        if wholesale_quantity > 0 and snapshot.get("wholesale_unit_price") is not None:
            unit_prices.append({
                "quantity": wholesale_quantity,
                "price_type": "wholesale",
                "unit_price": snapshot["wholesale_unit_price"],
            })
        if retail_quantity > 0 and snapshot.get("retail_unit_price") is not None:
            unit_prices.append({
                "quantity": retail_quantity,
                "price_type": "retail",
                "unit_price": snapshot["retail_unit_price"],
            })
        if not unit_prices:
            unit_prices.append({
                "quantity": _decimal(sale.quantity, "sold quantity"),
                "price_type": sale.price_type or "unit",
                "unit_price": sale.unit_price or "0.00",
            })
        lines.append(
            {
                "name": snapshot.get(
                    "name",
                    current_item.name if current_item is not None else "Item",
                ),
                "description": snapshot.get(
                    "description",
                    snapshot.get("name", current_item.name if current_item is not None else "Item"),
                ),
                "quantity": sale.quantity,
                "unit_prices": unit_prices,
                "total": sale.total_price,
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
            "event": event,
            "cashier": cashier.name if cashier else None,
            "lines": lines,
            "payments": [
                {
                    "created_at": _display_timestamp(payment.created_at),
                    "payment_method": payment.payment_method,
                    "amount": payment.amount,
                    "change_amount": payment.change_amount or "0.00",
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
