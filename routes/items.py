
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from starlette import status
from database_models import (
    Item,
    ItemCategory,
    ItemDiscount,
    PurchaseLines,
    PurchaseTxns,
    ResellerAllocationLines,
    ResellerTxns,
    SalesTxn,
    StockMvt,
)
from database import db_dependency
from models import CreateItemRequest, CategoryRequest, DiscountRequest, Role, StockAdjustmentRequest
from routes.auth import RoleChecker, get_current_user
from config import APP_TIMEZONE as CONFIGURED_TIMEZONE


router = APIRouter(
    prefix="/items",
    tags=["items"]
)
templates = Jinja2Templates(directory="templates")
user_dependency = Annotated[dict, Depends(get_current_user)]
MANAGEMENT_ACCESS = Depends(RoleChecker(Role.admin, Role.manager))
APP_TIMEZONE = CONFIGURED_TIMEZONE

def serialize_timestamp(value: datetime | str | None) -> str | None:
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

@router.get(
    "/catalogue",
    response_model=list[CreateItemRequest],
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))],
)
async def list_items(db: db_dependency):
    items = db.query(Item).all()
    return [
        CreateItemRequest(
            id=item.id,
            name=item.name,
            description=item.description,
            barcode=item.barcode,
            purchase_price=item.purchase_price,
            selling_price_wholesale=item.selling_price_wholesale,
            selling_price_retail=item.selling_price_retail,
            wholesale_threshold=item.wholesale_threshold or "6",
            quantity=item.quantity,
            unit=item.unit,
            created_at=serialize_timestamp(item.created_at),
            updated_at=serialize_timestamp(item.updated_at),
            category_id=item.category_id,
        )
        for item in items
    ]

@router.get("/{item_id}/discount", dependencies=[Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))])
async def item_discount(item_id: int, db: db_dependency):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    discounts = db.query(ItemDiscount).filter(ItemDiscount.active == 1).all()
    discount = next((d for d in discounts if d.discount_type == "item" and d.target_id == item.id), None)
    if discount is None:
        discount = next((d for d in discounts if d.discount_type == "category" and d.target_id == item.category_id), None)
    return {"percentage": discount.percentage if discount else "0"}


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def items_page(request: Request, user: user_dependency, db: db_dependency):
    items = db.query(Item).order_by(Item.name).all()
    categories = db.query(ItemCategory).order_by(ItemCategory.name).all()
    category_names = {category.id: category.name for category in categories}
    return templates.TemplateResponse(request, "items.html", {
        "user": user,
        "items": items,
        "categories": categories,
        "category_names": category_names,
    })


@router.post("/adjust-stock/{item_id}", status_code=status.HTTP_201_CREATED, dependencies=[MANAGEMENT_ACCESS])
async def adjust_stock(item_id: int, payload: StockAdjustmentRequest, db: db_dependency, user: user_dependency):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    timestamp = datetime.now(timezone.utc).isoformat()
    current = Decimal(str(item.quantity or "0"))
    item.quantity = str(current + payload.quantity)
    item.updated_at = timestamp
    db.add(StockMvt(item_id=item_id, quantity=str(payload.quantity), movement_type="in", created_at=timestamp, updated_at=timestamp))
    db.commit()
    return {"id": item.id, "quantity": item.quantity}


@router.get("/categories", response_class=HTMLResponse)
@router.get("/categories/manage", response_class=HTMLResponse, include_in_schema=False)
async def categories_page(request: Request, user: user_dependency, db: db_dependency):
    categories = db.query(ItemCategory).order_by(ItemCategory.name).all()
    return templates.TemplateResponse(request, "categories.html", {
        "user": user, "categories": categories,
    })


@router.get("/discounts", response_class=HTMLResponse)
async def discounts_page(request: Request, user: user_dependency, db: db_dependency):
    discounts = db.query(ItemDiscount).order_by(ItemDiscount.name).all()
    categories = db.query(ItemCategory).order_by(ItemCategory.name).all()
    items = db.query(Item).order_by(Item.name).all()
    return templates.TemplateResponse(request, "discounts.html", {
        "user": user,
        "discounts": discounts,
        "categories": categories,
        "items": items,
        "category_names": {category.id: category.name for category in categories},
        "item_names": {item.id: item.name for item in items},
    })


@router.post("/categories", status_code=201, dependencies=[MANAGEMENT_ACCESS])
async def create_category(payload: CategoryRequest, db: db_dependency):
    if db.query(ItemCategory).filter(ItemCategory.name.ilike(payload.name.strip())).first():
        raise HTTPException(status_code=409, detail="A category with that name already exists")
    timestamp = datetime.now(timezone.utc).isoformat()
    category = ItemCategory(name=payload.name.strip(), description=payload.description.strip(), created_at=timestamp, updated_at=timestamp)
    db.add(category)
    db.commit()
    db.refresh(category)
    return {"id": category.id, "name": category.name}


@router.put("/categories/{category_id}", dependencies=[MANAGEMENT_ACCESS])
async def update_category(category_id: int, payload: CategoryRequest, db: db_dependency):
    category = db.query(ItemCategory).filter(ItemCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    category.name = payload.name.strip()
    category.description = payload.description.strip()
    category.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    return {"id": category.id, "name": category.name}


@router.delete("/categories/{category_id}", status_code=204, dependencies=[MANAGEMENT_ACCESS])
async def delete_category(category_id: int, db: db_dependency):
    category = db.query(ItemCategory).filter(ItemCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if db.query(Item).filter(Item.category_id == category_id).first():
        raise HTTPException(status_code=409, detail="Category is assigned to one or more items")
    db.delete(category)
    db.commit()


@router.post("/discounts", status_code=201, dependencies=[MANAGEMENT_ACCESS])
async def create_discount(payload: DiscountRequest, db: db_dependency):
    target = db.query(Item if payload.discount_type == "item" else ItemCategory).filter((Item.id if payload.discount_type == "item" else ItemCategory.id) == payload.target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Discount target not found")
    timestamp = datetime.now(timezone.utc).isoformat()
    discount = ItemDiscount(name=payload.name.strip(), discount_type=payload.discount_type, target_id=payload.target_id, percentage=str(payload.percentage), active=1 if payload.active else 0, created_at=timestamp, updated_at=timestamp)
    db.add(discount)
    db.commit()
    db.refresh(discount)
    return {"id": discount.id}


@router.get("/import/page", response_class=HTMLResponse)
async def import_page(request: Request, user: user_dependency):
    return templates.TemplateResponse(request, "items_import.html", {"user": user})


@router.get("/import/template", dependencies=[MANAGEMENT_ACCESS])
async def download_import_template():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Items"
    headers = [
        "name",
        "description",
        "barcode",
        "category",
        "purchase_price",
        "selling_price_retail",
        "selling_price_wholesale",
        "wholesale_threshold",
        "quantity",
        "unit",
    ]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        width = max(len(str(cell.value or "")) for cell in column) + 2
        sheet.column_dimensions[column[0].column_letter].width = min(max(width, 12), 30)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="items_import_template.xlsx"'},
    )


@router.post("/import", dependencies=[MANAGEMENT_ACCESS])
async def import_items(file: UploadFile = File(...), db: db_dependency = None):
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=422, detail="Upload an Excel .xlsx or .xlsm file")
    try:
        workbook = load_workbook(BytesIO(await file.read()), read_only=True, data_only=True)
        sheet = workbook.active
    except Exception:
        raise HTTPException(status_code=422, detail="The uploaded file is not a valid Excel workbook") from None
    headers = [str(cell.value).strip().lower().replace(" ", "_") if cell.value is not None else "" for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
    required = {"name", "barcode", "purchase_price", "selling_price_retail", "selling_price_wholesale", "unit"}
    if not required.issubset(headers):
        raise HTTPException(status_code=422, detail="Required columns: name, barcode, purchase_price, selling_price_retail, selling_price_wholesale, unit")
    categories = {c.name.strip().lower(): c for c in db.query(ItemCategory).all()}
    created = updated = skipped = 0
    errors = []
    for row_number, values in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
        if not any(value is not None for value in values):
            continue
        row = dict(zip(headers, values))
        try:
            name = str(row["name"] or "").strip()
            barcode = str(row["barcode"] or "").strip()
            if not name or not barcode:
                raise ValueError("name and barcode are required")
            purchase_price = Decimal(str(row["purchase_price"]))
            retail = Decimal(str(row["selling_price_retail"]))
            wholesale = Decimal(str(row["selling_price_wholesale"]))
            quantity = Decimal(str(row.get("quantity") or 0))
            if any(value < 0 or not value.is_finite() for value in (purchase_price, retail, wholesale, quantity)):
                raise ValueError("prices and quantity must be non-negative")
            category_id = None
            category_name = str(row.get("category") or "").strip().lower()
            if category_name:
                category = categories.get(category_name)
                if not category:
                    timestamp = datetime.now(timezone.utc).isoformat()
                    category = ItemCategory(name=str(row.get("category") or "").strip(), created_at=timestamp, updated_at=timestamp)
                    db.add(category)
                    db.flush()
                    categories[category_name] = category
                category_id = category.id
        except (InvalidOperation, ValueError, TypeError) as exc:
            skipped += 1
            errors.append(f"Row {row_number}: {exc}")
            continue
        item = db.query(Item).filter(Item.barcode == barcode).first()
        if item:
            item.name, item.purchase_price = name, str(purchase_price)
            item.selling_price_retail, item.selling_price_wholesale = str(retail), str(wholesale)
            item.quantity, item.unit, item.category_id = str(quantity), str(row["unit"]).strip(), category_id
            item.description = str(row.get("description") or item.description or "")
            item.updated_at = datetime.now(timezone.utc).isoformat()
            updated += 1
        else:
            timestamp = datetime.now(timezone.utc).isoformat()
            item = Item(name=name, description=str(row.get("description") or ""), barcode=barcode, purchase_price=str(purchase_price), selling_price_retail=str(retail), selling_price_wholesale=str(wholesale), wholesale_threshold=str(row.get("wholesale_threshold") or 6), quantity=str(quantity), unit=str(row["unit"]).strip(), category_id=category_id, created_at=timestamp, updated_at=timestamp)
            db.add(item)
            created += 1
    db.commit()
    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors[:20]}


@router.post(
    "/create",
    status_code=201,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager))],
)
async def create_item(db: db_dependency, create_item_request: CreateItemRequest):
    create_item_model = Item(
        name=create_item_request.name,
        description=create_item_request.description,
        barcode=create_item_request.barcode,
        purchase_price=create_item_request.purchase_price,
        selling_price_wholesale=create_item_request.selling_price_wholesale,
        selling_price_retail=create_item_request.selling_price_retail,
        wholesale_threshold=str(create_item_request.wholesale_threshold),
        quantity=create_item_request.quantity,
        unit=create_item_request.unit,
        category_id=create_item_request.category_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )

    db.add(create_item_model)
    db.commit()

@router.get(
    "/{item_id}",
    response_model=CreateItemRequest,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))],
)
async def get_item(item_id: int, db: db_dependency):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return CreateItemRequest(
        id=item.id,
        name=item.name,
        description=item.description,
        barcode=item.barcode,
        purchase_price=item.purchase_price,
        selling_price_wholesale=item.selling_price_wholesale,
        selling_price_retail=item.selling_price_retail,
        wholesale_threshold=item.wholesale_threshold or "6",
        quantity=item.quantity,
        unit=item.unit,
        category_id=item.category_id,
        created_at=serialize_timestamp(item.created_at),
        updated_at=serialize_timestamp(item.updated_at)
    )

@router.put(
    "/{item_id}",
    response_model=CreateItemRequest,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager))],
)
async def update_item(item_id: int, update_item_request: CreateItemRequest, db: db_dependency):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.name = update_item_request.name
    item.description = update_item_request.description
    item.barcode = update_item_request.barcode
    item.purchase_price = update_item_request.purchase_price
    item.selling_price_wholesale = update_item_request.selling_price_wholesale
    item.selling_price_retail = update_item_request.selling_price_retail
    item.wholesale_threshold = str(update_item_request.wholesale_threshold)
    item.quantity = update_item_request.quantity
    item.unit = update_item_request.unit
    item.category_id = update_item_request.category_id
    item.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(item)
    return CreateItemRequest(
        id=item.id,
        name=item.name,
        description=item.description,
        barcode=item.barcode,
        purchase_price=item.purchase_price,
        selling_price_wholesale=item.selling_price_wholesale,
        selling_price_retail=item.selling_price_retail,
        wholesale_threshold=item.wholesale_threshold or "6",
        quantity=item.quantity,
        unit=item.unit,
        category_id=item.category_id,
        created_at=serialize_timestamp(item.created_at),
        updated_at=serialize_timestamp(item.updated_at),
    )

@router.delete(
    "/{item_id}",
    status_code=204,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager))],
)
async def delete_item(item_id: int, db: db_dependency):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    has_history = (
        db.query(SalesTxn.id).filter(SalesTxn.item_id == item_id).first()
        or db.query(PurchaseLines.id)
        .filter(PurchaseLines.item_id == item_id)
        .first()
        or db.query(PurchaseTxns.id).filter(PurchaseTxns.item_id == item_id).first()
        or db.query(ResellerAllocationLines.id)
        .filter(ResellerAllocationLines.item_id == item_id)
        .first()
        or db.query(ResellerTxns.id).filter(ResellerTxns.item_id == item_id).first()
    )
    if has_history:
        raise HTTPException(
            status_code=409,
            detail="Item has transaction or consignment history and cannot be deleted",
        )

    db.delete(item)
    db.commit()
