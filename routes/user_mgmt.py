
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Request
from passlib.context import CryptContext
from database_models import User
from database import db_dependency
from starlette import status
from models import CreateUserRequest, Role, UpdateUserRequest, UserResponse
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from routes.auth import RoleChecker, get_current_user
from typing import Annotated



router = APIRouter(
    prefix="/users",
    tags=["users"]
)

templates = Jinja2Templates(directory="templates")
user_dependency = Annotated[dict, Depends(get_current_user)]

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


def user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        name=user.name,
        username=user.username,
        email=user.email,
        phone=user.phone,
        role=user.role,
        created_at=serialize_timestamp(user.created_at),
        updated_at=serialize_timestamp(user.updated_at),
    )


@router.get(
    "/",
    response_class=HTMLResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager))],
)
async def list_users(request: Request, user: user_dependency, db: db_dependency):
    users = db.query(User).all()
    return templates.TemplateResponse(
        request,
        "user_mgmt.html",
        {
            "user": user,
            "users": users,
            "roles": list(Role) if user["role"] == Role.admin.value else [
                role for role in Role if role is not Role.admin
            ],
        },
    )


@router.post(
    "/create",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager))],
)
async def create_user(
    db: db_dependency,
    create_user_request: CreateUserRequest,
    current_user: user_dependency,
):
    if current_user["role"] == Role.manager.value and create_user_request.role is Role.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Managers cannot create admin accounts",
        )

    create_user_model = User(
        name=create_user_request.name,
        username = create_user_request.username,
        password = bcrypt_context.hash(create_user_request.password),
        email = create_user_request.email,
        phone = create_user_request.phone,
        role = create_user_request.role.value,
        created_at = datetime.now(timezone.utc),
        updated_at = datetime.now(timezone.utc)
    )

    db.add(create_user_model)
    db.commit()
    db.refresh(create_user_model)
    return user_response(create_user_model)

@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager))],
)
async def get_user(user_id: int, db: db_dependency, current_user: user_dependency):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user_response(user)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager))],
)
async def update_user(
    user_id: int,
    update_user_request: UpdateUserRequest,
    db: db_dependency,
    current_user: user_dependency,
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if current_user["role"] == Role.manager.value and (
        user.role == Role.admin.value or update_user_request.role is Role.admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Managers cannot edit admin accounts or assign the admin role",
        )
    if (
        user.role == Role.admin.value
        and update_user_request.role is not Role.admin
        and db.query(User).filter(User.role == Role.admin.value).count() <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The last admin account cannot be demoted",
        )

    user.name = update_user_request.name
    user.username = update_user_request.username
    user.email = update_user_request.email
    user.phone = update_user_request.phone
    user.role = update_user_request.role.value
    if update_user_request.password:
        user.password = bcrypt_context.hash(update_user_request.password)
    user.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user)
    return user_response(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RoleChecker(Role.admin, Role.manager))],
)
async def delete_user(user_id: int, db: db_dependency, current_user: user_dependency):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if current_user["role"] == Role.manager.value and user.role == Role.admin.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Managers cannot delete admin accounts",
        )
    if user.id == current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot delete your own account",
        )
    if (
        user.role == Role.admin.value
        and db.query(User).filter(User.role == Role.admin.value).count() <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The last admin account cannot be deleted",
        )

    db.delete(user)
    db.commit()
