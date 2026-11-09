import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import db_dependency
from database_models import Contact, Invoices, Item, Payments, Quotations
from models import DocumentRequest, Role
from routes.auth import RoleChecker, get_current_user
from routes.settings import get_settings
from routes.ledger_utils import decimal_value, format_money, money
from config import CURRENCY_CODE


router = APIRouter(tags=["documents"])
templates = Jinja2Templates(directory="templates")
templates.env.filters["money"] = format_money
user_dependency = Annotated[dict, Depends(get_current_user)]
DOCUMENT_ACCESS = Depends(RoleChecker(Role.admin, Role.manager))


def _document_number(db, prefix: str, model) -> str:
    year = datetime.now(timezone.utc).strftime("%Y")
    highest = 0
    for row in db.query(model).filter(model.document_number.isnot(None)).all():
        number = row.document_number or ""
        if number.startswith(f"{prefix}-{year}-"):
            try:
                highest = max(highest, int(number.rsplit("-", 1)[-1]))
            except ValueError:
                pass
    return f"{prefix}-{year}-{highest + 1:04d}"


def _line_snapshot(db, line) -> dict:
    item = db.query(Item).filter(Item.id == line.item_id).first() if line.item_id else None
    quantity = money(line.quantity)
    unit_price = money(line.unit_price)
    discount = money(unit_price * quantity * line.discount_percentage / Decimal("100"))
    line_total = money(unit_price * quantity - discount)
    return {
        "item_id": line.item_id,
        "description": line.description or (item.name if item else "Item"),
        "quantity": str(quantity),
        "unit_price": str(unit_price),
        "discount_percentage": str(line.discount_percentage),
        "discount_amount": str(discount),
        "line_total": str(line_total),
    }


def _load_items(db, customer_id: int) -> tuple[list, list]:
    items = db.query(Item).order_by(Item.name).all()
    customers = (
        db.query(Contact)
        .filter(Contact.contact_type == "customer")
        .order_by(Contact.name)
        .all()
    )
    return items, customers


def _totals(lines: list[dict], tax_rate: Decimal, discount_amount: Decimal) -> dict:
    subtotal = sum((decimal_value(line["line_total"], "line total") for line in lines), Decimal("0"))
    discounted = max(subtotal - money(discount_amount), Decimal("0"))
    tax_amount = money(discounted * tax_rate / Decimal("100"))
    return {
        "subtotal": money(subtotal),
        "discount_amount": money(discount_amount),
        "tax_amount": tax_amount,
        "total": money(discounted + tax_amount),
    }


def _document_amount_text(currency: str, amount: Decimal, label: str) -> str:
    return f"{label}: {currency} {money(amount):,.2f}"


def _metadata_value(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in {"", "none", "null"} else text


def _document_issue_date(document) -> str | None:
    issue_date = _metadata_value(document.issue_date)
    if issue_date:
        return issue_date
    created_at = _metadata_value(document.created_at)
    if not created_at:
        return None
    try:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return created_at[:10] if len(created_at) >= 10 else created_at


@router.get("/quotations", response_class=HTMLResponse, dependencies=[DOCUMENT_ACCESS])
async def quotations_page(request: Request, user: user_dependency, db: db_dependency):
    items = db.query(Item).order_by(Item.name).all()
    customers = db.query(Contact).filter(Contact.contact_type == "customer").order_by(Contact.name).all()
    customer_names = {customer.id: customer.name for customer in customers}
    quotations = db.query(Quotations).order_by(Quotations.id.desc()).all()
    return templates.TemplateResponse(request, "document_list.html", {
        "user": user, "document_type": "quotation", "documents": quotations,
        "items": items, "customers": customers, "customer_names": customer_names,
    })


@router.post("/quotations", dependencies=[DOCUMENT_ACCESS])
async def create_quotation(payload: DocumentRequest, user: user_dependency, db: db_dependency):
    customer = db.query(Contact).filter(Contact.id == payload.customer_id, Contact.contact_type == "customer").first()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    lines = [_line_snapshot(db, line) for line in payload.lines]
    totals = _totals(lines, money(payload.tax_rate), money(payload.discount_amount))
    timestamp = datetime.now(timezone.utc).isoformat()
    quotation = Quotations(
        customer_id=payload.customer_id,
        document_number=payload.document_number or _document_number(db, get_settings(db)["quotation_prefix"], Quotations),
        issue_date=payload.issue_date,
        expiry_date=payload.expiry_date,
        notes=payload.notes,
        subtotal=str(totals["subtotal"]),
        tax_rate=str(payload.tax_rate),
        tax_amount=str(totals["tax_amount"]),
        discount_amount=str(totals["discount_amount"]),
        currency=payload.currency.upper(),
        items=json.dumps(lines),
        total_price=str(totals["total"]),
        status="draft",
        created_by=user["id"],
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(quotation)
    db.commit()
    db.refresh(quotation)
    return {"message": "Quotation created", "id": quotation.id, "print_url": f"/quotations/{quotation.id}/print"}


@router.get("/invoices", response_class=HTMLResponse, dependencies=[DOCUMENT_ACCESS])
async def invoices_page(request: Request, user: user_dependency, db: db_dependency):
    invoices = db.query(Invoices).order_by(Invoices.id.desc()).all()
    items = db.query(Item).order_by(Item.name).all()
    customers = db.query(Contact).filter(Contact.contact_type == "customer").order_by(Contact.name).all()
    customer_names = {customer.id: customer.name for customer in customers}
    return templates.TemplateResponse(request, "document_list.html", {
        "user": user, "document_type": "invoice", "documents": invoices,
        "items": items, "customers": customers, "customer_names": customer_names,
    })


@router.post("/invoices", dependencies=[DOCUMENT_ACCESS])
async def create_invoice(payload: DocumentRequest, user: user_dependency, db: db_dependency):
    customer = db.query(Contact).filter(Contact.id == payload.customer_id, Contact.contact_type == "customer").first()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    lines = [_line_snapshot(db, line) for line in payload.lines]
    totals = _totals(lines, money(payload.tax_rate), money(payload.discount_amount))
    timestamp = datetime.now(timezone.utc).isoformat()
    invoice = Invoices(
        customer_id=payload.customer_id,
        document_number=payload.document_number or _document_number(db, get_settings(db)["invoice_prefix"], Invoices),
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        notes=payload.notes,
        subtotal=str(totals["subtotal"]),
        tax_rate=str(payload.tax_rate),
        tax_amount=str(totals["tax_amount"]),
        discount_amount=str(totals["discount_amount"]),
        currency=payload.currency.upper(),
        items=json.dumps(lines),
        total_price=str(totals["total"]),
        status="unpaid",
        created_by=user["id"],
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return {"message": "Invoice created", "id": invoice.id, "print_url": f"/invoices/{invoice.id}/print"}


@router.post("/quotations/{quotation_id}/convert", dependencies=[DOCUMENT_ACCESS])
async def convert_quotation(quotation_id: int, user: user_dependency, db: db_dependency):
    quotation = db.query(Quotations).filter(Quotations.id == quotation_id).first()
    if quotation is None:
        raise HTTPException(status_code=404, detail="Quotation not found")
    timestamp = datetime.now(timezone.utc).isoformat()
    invoice = Invoices(
        customer_id=quotation.customer_id,
        document_number=_document_number(db, get_settings(db)["invoice_prefix"], Invoices),
        issue_date=datetime.now(timezone.utc).date().isoformat(),
        due_date=quotation.expiry_date,
        notes=quotation.notes,
        subtotal=quotation.subtotal,
        tax_rate=quotation.tax_rate,
        tax_amount=quotation.tax_amount,
        discount_amount=quotation.discount_amount,
        currency=quotation.currency,
        items=quotation.items,
        total_price=quotation.total_price,
        status="unpaid",
        created_by=user["id"],
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(invoice)
    quotation.status = "converted"
    quotation.updated_at = timestamp
    db.commit()
    db.refresh(invoice)
    return {"message": "Quotation converted to invoice", "id": invoice.id, "print_url": f"/invoices/{invoice.id}/print"}


def _render_document(request, user, db, model, document_id, document_type):
    document = db.query(model).filter(model.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail=f"{document_type.title()} not found")
    documents = db.query(model).order_by(model.id.desc()).all()
    customer_ids = {row.customer_id for row in documents if row.customer_id is not None}
    customers = (
        db.query(Contact).filter(Contact.id.in_(customer_ids)).all()
        if customer_ids
        else []
    )
    customers_by_id = {row.id: row for row in customers}
    customer = customers_by_id.get(document.customer_id)
    paid_by_invoice = {}
    if document_type == "invoice" and documents:
        payments = (
            db.query(Payments)
            .filter(
                Payments.invoice_id.in_([row.id for row in documents]),
                Payments.status == "completed",
            )
            .all()
        )
        for payment in payments:
            paid_by_invoice[payment.invoice_id] = (
                paid_by_invoice.get(payment.invoice_id, Decimal("0"))
                + decimal_value(payment.amount, "customer payment")
            )

    preview_items = []
    for row in documents:
        total = decimal_value(row.total_price, "document total")
        amount = (
            max(total - paid_by_invoice.get(row.id, Decimal("0")), Decimal("0"))
            if document_type == "invoice"
            else total
        )
        row_customer = customers_by_id.get(row.customer_id)
        reference = _metadata_value(row.document_number) or f"{document_type.title()} #{row.id}"
        issue_date = _document_issue_date(row)
        detail = f"{reference} - {issue_date}" if issue_date else reference
        preview_items.append({
            "href": f"/{document_type}s/{row.id}/print",
            "title": row_customer.name if row_customer else "Customer",
            "detail": detail,
            "amount_text": _document_amount_text(
                row.currency or CURRENCY_CODE,
                amount,
                "Due" if document_type == "invoice" else "Total",
            ),
            "status": row.status or "",
            "active": row.id == document.id,
        })

    try:
        lines = json.loads(document.items or "[]")
    except json.JSONDecodeError:
        lines = []
    subtotal = decimal_value(document.subtotal or document.total_price, "subtotal")
    tax_amount = decimal_value(document.tax_amount or "0", "tax amount")
    discount_amount = decimal_value(document.discount_amount or "0", "discount amount")
    return templates.TemplateResponse(request, "document_print.html", {
        "user": user,
        "document": document,
        "document_type": document_type,
        "display_document_number": (
            _metadata_value(document.document_number)
            or f"{document_type.title()} #{document.id}"
        ),
        "display_issue_date": _document_issue_date(document),
        "display_deadline": _metadata_value(
            document.due_date if document_type == "invoice" else document.expiry_date
        ),
        "customer": customer,
        "preview_list_title": "Invoices" if document_type == "invoice" else "Quotes",
        "preview_items": preview_items,
        "lines": lines,
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "discount_amount": discount_amount,
        "total": decimal_value(document.total_price, "document total"),
        "currency": document.currency or CURRENCY_CODE,
    })


@router.get("/quotations/{document_id}/print", response_class=HTMLResponse, dependencies=[DOCUMENT_ACCESS])
async def print_quotation(document_id: int, request: Request, user: user_dependency, db: db_dependency):
    return _render_document(request, user, db, Quotations, document_id, "quotation")


@router.get("/invoices/{document_id}/print", response_class=HTMLResponse, dependencies=[DOCUMENT_ACCESS])
async def print_invoice(document_id: int, request: Request, user: user_dependency, db: db_dependency):
    return _render_document(request, user, db, Invoices, document_id, "invoice")
