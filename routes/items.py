
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from database_models import Item
from database import db_dependency
from models import CreateItemRequest, Role
from routes.auth import RoleChecker


router = APIRouter(
    prefix="/items",
    tags=["items"]
)

APP_TIMEZONE = ZoneInfo("Africa/Harare")

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
    "/",
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
            updated_at=serialize_timestamp(item.updated_at)
        )
        for item in items
    ]

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
    item.updated_at = datetime.now(timezone.utc)

    db.commit()

@router.delete(
    "/{item_id}",
    status_code=204,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager))],
)
async def delete_item(item_id: int, db: db_dependency):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(item)
    db.commit()
