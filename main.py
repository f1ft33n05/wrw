import logging
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from database import engine, init_db, db_dependency
import database_models
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException
import routes.auth as auth
import routes.user_mgmt as user_mgmt
import routes.contacts as contacts
import routes.items as items
import routes.sales as sales
from routes.auth import get_current_user
from models import Role
from routes.auth import RoleChecker
from typing import Annotated

app = FastAPI()
app.include_router(auth.router)
app.include_router(user_mgmt.router)
app.include_router(contacts.router)
app.include_router(items.router)
app.include_router(sales.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)


def wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "").lower()


def render_error_page(request: Request, status_code: int, detail: str) -> Response:
    template_name = f"errors/{status_code}.html"
    return templates.TemplateResponse(
        request,
        template_name,
        {"status_code": status_code, "detail": detail},
        status_code=status_code,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> Response:
    if wants_html(request) and exc.status_code in {401, 404, 500}:
        return render_error_page(request, exc.status_code, str(exc.detail))
    return JSONResponse(
        {"detail": exc.detail},
        status_code=exc.status_code,
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> Response:
    logger.error(
        "Unhandled application exception",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    if wants_html(request):
        return render_error_page(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Something went wrong. Please try again later.",
        )
    return JSONResponse(
        {"detail": "Internal Server Error"},
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )

database_models.Base.metadata.create_all(bind=engine)

user_dependency = Annotated[dict, Depends(get_current_user)]


init_db()

@app.get("/", response_class=HTMLResponse, status_code=status.HTTP_200_OK)
async def root(request: Request):
    return templates.TemplateResponse(request, "auth.html")

@app.get(
    "/dashboard",
    response_class=HTMLResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(RoleChecker(Role.admin, Role.manager, Role.cashier))
    ],
)
async def dashboard(request: Request, user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        
    return templates.TemplateResponse(request, "dashboard.html", {"user": user})
