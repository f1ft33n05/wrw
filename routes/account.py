from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from starlette import status

from database import db_dependency
from database_models import User
from routes.auth import get_current_user


router = APIRouter(tags=["account"])
templates = Jinja2Templates(directory="templates")
user_dependency = Annotated[dict, Depends(get_current_user)]
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.get("/profile", response_class=HTMLResponse)
async def profile(request: Request, current_user: user_dependency, db: db_dependency):
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return templates.TemplateResponse(request, "profile.html", {"user": current_user, "profile": user})


@router.post("/profile")
async def update_profile(
    request: Request,
    current_user: user_dependency,
    db: db_dependency,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    current_password: str = Form(default=""),
    new_password: str = Form(default=""),
):
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    name = name.strip()
    email = email.strip().lower()
    phone = phone.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name is required")

    if db.query(User).filter(User.email == email, User.id != user.id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already in use")
    if db.query(User).filter(User.phone == phone, User.id != user.id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone number is already in use")

    if new_password:
        if not current_password or not password_context.verify(current_password, user.password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
        if len(new_password.encode("utf-8")) > 72 or len(new_password) < 8:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at least 8 characters and no more than 72 bytes")

    user.name = name
    user.email = email
    user.phone = phone
    if new_password:
        user.password = password_context.hash(new_password)
    db.commit()
    return RedirectResponse(url="/profile?updated=1", status_code=status.HTTP_303_SEE_OTHER)
