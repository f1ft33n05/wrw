import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from starlette import status

from database import db_dependency
from database_models import (
    Contact,
    Invoices,
    Item,
    PurchaseLines,
    Purchases,
    SalesTxn,
)
from models import Role
from routes.auth import RoleChecker, get_current_user


router = APIRouter(tags=["reports"])
templates = Jinja2Templates(directory="templates")
REPORT_ACCESS = Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))
REPORT_TYPES = {
    "sales": "Sales report",
    "inventory": "Inventory report",
    "trending": "Trending products",
    "purchases": "Purchase report",
    "purchase-sale": "Purchase & sale report",
}
user_dependency = Annotated[dict, Depends(get_current_user)]


def decimal_value(value, default="0"):
    try:
        result = Decimal(str(value or default))
    except (InvalidOperation, ValueError):
        return Decimal(default)
    return result if result.is_finite() else Decimal(default)


def money(value):
    return f"{decimal_value(value):,.2f}"


def report_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.date().isoformat()
        except ValueError:
            return value[:10]
    return ""


def in_period(value, date_from: str | None, date_to: str | None):
    date = report_date(value)
    return (not date_from or date >= date_from) and (not date_to or date <= date_to)


def safe_number(value):
    return decimal_value(value)


def sales_data(db, date_from, date_to):
    rows = []
    invoices = db.query(Invoices).order_by(Invoices.created_at.desc()).all()
    customer_ids = {row.customer_id for row in invoices if row.customer_id}
    customers = {
        row.id: row.name
        for row in (
            db.query(Contact).filter(Contact.id.in_(customer_ids)).all()
            if customer_ids else []
        )
    }
    for invoice in invoices:
        if not in_period(invoice.created_at, date_from, date_to):
            continue
        rows.append({
            "Date": report_date(invoice.created_at),
            "Invoice": invoice.document_number or str(invoice.id),
            "Customer": customers.get(invoice.customer_id, "Walk-in customer"),
            "Total": money(invoice.total_price),
            "Status": (invoice.status or "").replace("_", " ").title(),
        })
    return ["Date", "Invoice", "Customer", "Total", "Status"], rows


def inventory_data(db):
    rows = []
    items = db.query(Item).order_by(Item.name).all()
    for item in items:
        quantity = safe_number(item.quantity)
        cost_value = quantity * safe_number(item.purchase_price)
        rows.append({
            "Item": item.name,
            "SKU / Barcode": item.barcode or "",
            "Quantity": f"{quantity:f}".rstrip("0").rstrip("."),
            "Unit": item.unit or "",
            "Purchase price": money(item.purchase_price),
            "Stock value": money(cost_value),
        })
    return ["Item", "SKU / Barcode", "Quantity", "Unit", "Purchase price", "Stock value"], rows


def trending_data(db, date_from, date_to):
    sales = db.query(SalesTxn).all()
    item_ids = {sale.item_id for sale in sales if sale.item_id}
    items = {
        item.id: item
        for item in (
            db.query(Item).filter(Item.id.in_(item_ids)).all()
            if item_ids else []
        )
    }
    totals = {}
    for sale in sales:
        if not in_period(sale.created_at, date_from, date_to):
            continue
        quantity = safe_number(sale.quantity)
        revenue = safe_number(sale.total_price)
        current = totals.setdefault(sale.item_id, {"quantity": Decimal("0"), "revenue": Decimal("0"), "transactions": 0})
        current["quantity"] += quantity
        current["revenue"] += revenue
        current["transactions"] += 1
    rows = []
    for item_id, totals_row in totals.items():
        item = items.get(item_id)
        rows.append({
            "Product": item.name if item else f"Item #{item_id}",
            "Barcode": item.barcode if item else "",
            "Quantity sold": f"{totals_row['quantity']:f}".rstrip("0").rstrip("."),
            "Transactions": totals_row["transactions"],
            "Sales value": money(totals_row["revenue"]),
        })
    rows.sort(key=lambda row: decimal_value(row["Sales value"].replace(",", "")), reverse=True)
    return ["Product", "Barcode", "Quantity sold", "Transactions", "Sales value"], rows


def purchases_data(db, date_from, date_to):
    rows = []
    purchases = db.query(Purchases).order_by(Purchases.created_at.desc()).all()
    supplier_ids = {purchase.supplier_id for purchase in purchases if purchase.supplier_id}
    suppliers = {
        row.id: row.name
        for row in (
            db.query(Contact).filter(Contact.id.in_(supplier_ids)).all()
            if supplier_ids else []
        )
    }
    for purchase in purchases:
        if not in_period(purchase.created_at, date_from, date_to):
            continue
        rows.append({
            "Date": report_date(purchase.created_at),
            "Purchase": f"PO-{purchase.id}",
            "Supplier": suppliers.get(purchase.supplier_id, "Unknown supplier"),
            "Total": money(purchase.total_amount),
        })
    return ["Date", "Purchase", "Supplier", "Total"], rows


def purchase_sale_data(db, date_from, date_to):
    items = {item.id: item for item in db.query(Item).all()}
    purchases_by_id = {purchase.id: purchase for purchase in db.query(Purchases).all()}
    purchase_totals = {}
    purchase_quantities = {}
    for line in db.query(PurchaseLines).all():
        purchase = purchases_by_id.get(line.purchase_id)
        if not purchase or not in_period(purchase.created_at, date_from, date_to):
            continue
        purchase_quantities[line.item_id] = purchase_quantities.get(line.item_id, Decimal("0")) + safe_number(line.quantity)
        purchase_totals[line.item_id] = purchase_totals.get(line.item_id, Decimal("0")) + safe_number(line.total_amount)

    sales_quantities = {}
    sales_totals = {}
    for sale in db.query(SalesTxn).all():
        if not in_period(sale.created_at, date_from, date_to):
            continue
        sales_quantities[sale.item_id] = sales_quantities.get(sale.item_id, Decimal("0")) + safe_number(sale.quantity)
        sales_totals[sale.item_id] = sales_totals.get(sale.item_id, Decimal("0")) + safe_number(sale.total_price)

    rows = []
    for item_id in sorted(set(purchase_quantities) | set(sales_quantities), key=lambda value: items.get(value).name if items.get(value) else str(value)):
        item = items.get(item_id)
        rows.append({
            "Product": item.name if item else f"Item #{item_id}",
            "Purchased qty": f"{purchase_quantities.get(item_id, Decimal('0')):f}".rstrip("0").rstrip("."),
            "Purchase value": money(purchase_totals.get(item_id, Decimal("0"))),
            "Sold qty": f"{sales_quantities.get(item_id, Decimal('0')):f}".rstrip("0").rstrip("."),
            "Sales value": money(sales_totals.get(item_id, Decimal("0"))),
            "Gross difference": money(sales_totals.get(item_id, Decimal("0")) - purchase_totals.get(item_id, Decimal("0"))),
        })
    return ["Product", "Purchased qty", "Purchase value", "Sold qty", "Sales value", "Gross difference"], rows


def report_data(db, report_type, date_from=None, date_to=None):
    if report_type == "sales":
        return sales_data(db, date_from, date_to)
    if report_type == "inventory":
        return inventory_data(db)
    if report_type == "trending":
        return trending_data(db, date_from, date_to)
    if report_type == "purchases":
        return purchases_data(db, date_from, date_to)
    if report_type == "purchase-sale":
        return purchase_sale_data(db, date_from, date_to)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")


@router.get("/reports", response_class=HTMLResponse, dependencies=[REPORT_ACCESS])
async def reports_page(
    request: Request,
    user: user_dependency,
    db: db_dependency,
    report_type: str = Query("sales", alias="type"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    if report_type not in REPORT_TYPES:
        report_type = "sales"
    columns, rows = report_data(db, report_type, date_from, date_to)
    return templates.TemplateResponse(request, "reports.html", {
        "user": user,
        "report_type": report_type,
        "report_types": REPORT_TYPES,
        "report_title": REPORT_TYPES[report_type],
        "columns": columns,
        "rows": rows,
        "date_from": date_from or "",
        "date_to": date_to or "",
        "row_count": len(rows),
    })


@router.get("/reports/export/{file_format}", dependencies=[REPORT_ACCESS])
async def export_report(
    file_format: str,
    db: db_dependency,
    report_type: str = Query("sales", alias="type"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    if report_type not in REPORT_TYPES:
        raise HTTPException(status_code=404, detail="Report not found")
    columns, rows = report_data(db, report_type, date_from, date_to)
    title = REPORT_TYPES[report_type]
    filename = report_type.replace("-", "_")

    if file_format == "csv":
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )

    if file_format == "xlsx":
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = title[:31]
        worksheet.append([title])
        worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(columns))
        worksheet["A1"].font = Font(size=16, bold=True, color="FFFFFF")
        worksheet["A1"].fill = PatternFill("solid", fgColor="6D2C91")
        worksheet["A1"].alignment = Alignment(horizontal="center")
        worksheet.append(columns)
        for cell in worksheet[2]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="8B4DB5")
        for row in rows:
            worksheet.append([row.get(column, "") for column in columns])
        for index, column in enumerate(columns, start=1):
            worksheet.column_dimensions[worksheet.cell(1, index).column_letter].width = max(12, min(35, len(column) + 4))
        for row in worksheet.iter_rows(min_row=3):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
        )

    if file_format == "pdf":
        output = BytesIO()
        page_size = landscape(A4)
        document = SimpleDocTemplate(output, pagesize=page_size, title=title)
        styles = getSampleStyleSheet()
        story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
        table_data = [columns] + [[str(row.get(column, "")) for column in columns] for row in rows]
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6D2C91")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4EDF7")]),
        ]))
        story.append(table)
        document.build(story)
        output.seek(0)
        return StreamingResponse(output, media_type="application/pdf",
                                 headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'})

    raise HTTPException(status_code=404, detail="Unsupported export format")


@router.get("/sales_report", include_in_schema=False, dependencies=[REPORT_ACCESS])
async def legacy_sales_report():
    return RedirectResponse(url="/reports?type=sales", status_code=302)


@router.get("/stock_report", include_in_schema=False, dependencies=[REPORT_ACCESS])
async def legacy_stock_report():
    return RedirectResponse(url="/reports?type=inventory", status_code=302)


@router.get("/purchase_sale_report", include_in_schema=False, dependencies=[REPORT_ACCESS])
async def legacy_purchase_sale_report():
    return RedirectResponse(url="/reports?type=purchase-sale", status_code=302)
