import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from database_models import User
from database import db_dependency
from starlette import status
from typing import Annotated
from models import Role, Token

load_dotenv()  # loads .env in the project root

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/token', auto_error=False)


@router.post("/token", response_model=Token)
async def generate_access_token(db: db_dependency, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_expires = timedelta(minutes=20)
    token = create_access_token(user.username, user.id, user.role, expires_delta=token_expires)

    return {"access_token": token, "token_type": "bearer"}

@router.post("/login")
async def login(
    request: Request,
    db: db_dependency,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_expires = timedelta(minutes=20)
    token = create_access_token(user.username, user.id, user.role, expires_delta=token_expires)
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=int(token_expires.total_seconds()),
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
    )
    return response

@router.post("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        secure=request.url.scheme == "https",
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
        expire = datetime.now(timezone.utc) + timedelta(minutes=20)
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
        return {"username": user.username, "id": user.id, "role": user.role}
    except JWTError:
        raise credentials_exception


class RoleChecker:
    def __init__(self, *allowed_roles: Role):
        self.allowed_roles = {role.value for role in allowed_roles}

    async def __call__(
        self,
        current_user: Annotated[dict, Depends(get_current_user)],
    ):
        if current_user["role"] not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )