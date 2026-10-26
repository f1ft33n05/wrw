
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException
from passlib.context import CryptContext
from database_models import User
from database import db_dependency
from starlette import status
from models import CreateUserRequest


router = APIRouter(
    prefix="/users",
    tags=["users"]
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

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

@router.get("/", response_model=list[CreateUserRequest])
async def list_users(db: db_dependency):
    users = db.query(User).all()
    return [
        CreateUserRequest(
            id=user.id,
            username=user.username,
            password=user.password,
            email=user.email,
            phone=user.phone,
            role=user.role,
            created_at=serialize_timestamp(user.created_at),
            updated_at=serialize_timestamp(user.updated_at)
        )
        for user in users
    ]


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency, create_user_request: CreateUserRequest):
    create_user_model = User(
        username = create_user_request.username,
        password = bcrypt_context.hash(create_user_request.password),
        email = create_user_request.email,
        phone = create_user_request.phone,
        role = create_user_request.role,
        created_at = datetime.now(timezone.utc),
        updated_at = datetime.now(timezone.utc)
    )

    db.add(create_user_model)
    db.commit()

@router.get("/{user_id}", response_model=CreateUserRequest)
async def get_user(user_id: int, db: db_dependency):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return CreateUserRequest(
        username=user.username,
        password=user.password,
        email=user.email,
        phone=user.phone,
        role=user.role,
        created_at=serialize_timestamp(user.created_at),
        updated_at=serialize_timestamp(user.updated_at)
    )

@router.put("/{user_id}", response_model=CreateUserRequest)
async def update_user(user_id: int, update_user_request: CreateUserRequest, db: db_dependency):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.username = update_user_request.username
    user.password = bcrypt_context.hash(update_user_request.password)
    user.email = update_user_request.email
    user.phone = update_user_request.phone
    user.role = update_user_request.role
    user.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user)

    return CreateUserRequest(
        username=user.username,
        password=user.password,
        email=user.email,
        phone=user.phone,
        role=user.role,
        created_at=serialize_timestamp(user.created_at),
        updated_at=serialize_timestamp(user.updated_at)
    )

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: db_dependency):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    db.delete(user)
    db.commit()