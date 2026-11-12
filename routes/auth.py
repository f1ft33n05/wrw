from datetime import datetime, timedelta, timezone
from math import ceil
import time
from fastapi import APIRouter, HTTPException, Depends, Form
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext
from database_models import Invoices, User, RolePermission
from database import db_dependency
from starlette import status
from typing import Annotated
from models import Role, Token
from config import ACCESS_TOKEN_EXPIRE_MINUTES, ENVIRONMENT, JWT_ALGORITHM, SECRET_KEY
from audit import record_audit_event

ALGORITHM = JWT_ALGORITHM

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)
templates = Jinja2Templates(directory="templates")

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/token', auto_error=False)

login_attempts: dict[str, list[float]] = {}
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 5 * 60


def safe_return_path(value: str | None) -> str | None:
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return None
    return value


def _check_login_rate_limit(request: Request) -> None:
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    recent = [
        timestamp
        for timestamp in login_attempts.get(key, [])
        if now - timestamp < LOGIN_RATE_LIMIT_WINDOW_SECONDS
    ]
    login_attempts[key] = recent
    if len(recent) >= 5:
        retry_after = max(
            1,
            ceil(LOGIN_RATE_LIMIT_WINDOW_SECONDS - (now - recent[0])),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again in",
            headers={"Retry-After": str(retry_after)},
        )


def _record_failed_login(request: Request) -> None:
    key = request.client.host if request.client else "unknown"
    recent = login_attempts.get(key, [])
    recent.append(time.monotonic())
    login_attempts[key] = recent


@router.post("/token", response_model=Token)
async def generate_access_token(db: db_dependency, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(user.username, user.id, user.role, expires_delta=token_expires)

    return {"access_token": token, "token_type": "bearer"}

@router.post("/login")
async def login(
    request: Request,
    db: db_dependency,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    next_path: Annotated[str | None, Form(alias="next")] = None,
):
    try:
        _check_login_rate_limit(request)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
            raise
        return templates.TemplateResponse(
            request,
            "auth.html",
            {
                "error_message": exc.detail,
                "retry_after_seconds": int(exc.headers["Retry-After"]),
                "next_path": safe_return_path(next_path),
            },
            status_code=exc.status_code,
        )

    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        _record_failed_login(request)
        record_audit_event(db, action="auth.login", outcome="failure", ip_address=request.client.host if request.client else None)
        db.commit()
        return templates.TemplateResponse(
            request,
            "auth.html",
            {
                "error_message": "Incorrect username or password",
                "next_path": safe_return_path(next_path),
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(user.username, user.id, user.role, expires_delta=token_expires)
    response = RedirectResponse(
        url=safe_return_path(next_path) or "/dashboard",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=int(token_expires.total_seconds()),
        httponly=True,
        secure=ENVIRONMENT == "production" or request.url.scheme == "https",
        samesite="lax",
    )
    record_audit_event(db, action="auth.login", outcome="success", actor={"id": user.id, "username": user.username}, ip_address=request.client.host if request.client else None)
    db.commit()
    return response

@router.post("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        secure=ENVIRONMENT == "production" or request.url.scheme == "https",
        samesite="lax",
    )
    return response


def authenticate_user(db, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False

    try:
        if len(password.encode("utf-8")) > 72:
            return False
        if not bcrypt_context.verify(password, user.password):
            return False
    except (ValueError, TypeError):
        return False

    return user

def create_access_token(username: str, user_id: int, role: str, expires_delta: timedelta):
    encode = {"sub": username, "role": role, 'id': user_id}
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    encode.update({"exp": expire})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_bearer)],
    db: db_dependency,
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials"
    )
    token = token or request.cookies.get("access_token")
    if token is None:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user_id = payload.get("id")
        if not isinstance(username, str) or not isinstance(user_id, int):
            raise credentials_exception
        user = db.query(User).filter(User.id == user_id).first()
        if user is None or user.username != username:
            raise credentials_exception
        current_user = {
            "username": user.username,
            "name": user.name,
            "id": user.id,
            "role": user.role,
        }
        is_html_page_request = (
            request.method in {"GET", "HEAD"}
            and "text/html" in request.headers.get("accept", "").lower()
        )
        if is_html_page_request:
            paused_draft = (
                db.query(Invoices.id)
                .filter(
                    Invoices.created_by == user.id,
                    Invoices.status == "draft",
                    Invoices.document_number.is_(None),
                )
                .order_by(Invoices.id.desc())
                .first()
            )
            current_user["paused_pos_draft_id"] = paused_draft[0] if paused_draft else None
        return current_user
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please log in again.",
            headers={"X-Session-Expired": "true"},
        )
    except JWTError:
        raise credentials_exception


class RoleChecker:
    def __init__(self, *allowed_roles: Role, module: str | None = None, action: str = "can_view"):
        self.allowed_roles = {role.value for role in allowed_roles}
        self.module = module
        if action not in {"can_view", "can_create", "can_edit", "can_delete"}:
            raise ValueError("Invalid role permission action")
        self.action = action

    async def __call__(
        self,
        current_user: Annotated[dict, Depends(get_current_user)],
        db: db_dependency,
    ):
        if current_user["role"] in self.allowed_roles:
            return
        if self.module:
            permission = db.query(RolePermission).filter(
                RolePermission.role_name == current_user["role"],
                RolePermission.module == self.module,
                getattr(RolePermission, self.action) == 1,
            ).first()
            if permission:
                return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource",
        )