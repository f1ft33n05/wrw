import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import time
import uuid
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from database import engine, init_db, db_dependency
import database_models
from database_models import Invoices, Payments, Purchases, SupplierPayments
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException
import routes.auth as auth
import routes.user_mgmt as user_mgmt
import routes.contacts as contacts
import routes.items as items
import routes.sales as sales
import routes.purchases as purchases
import routes.resellers as resellers
import routes.events as events
import routes.documents as documents
import routes.reports as reports
import routes.roles as roles
from routes.auth import get_current_user
from models import Role
from routes.auth import RoleChecker
from typing import Annotated
from sqlalchemy import text

app = FastAPI()
app.include_router(auth.router)
app.include_router(user_mgmt.router)
app.include_router(contacts.router)
app.include_router(contacts.pages_router)
app.include_router(items.router)
app.include_router(sales.router)
app.include_router(purchases.router)
app.include_router(resellers.router)
app.include_router(events.router)
app.include_router(documents.router)
app.include_router(reports.router)
app.include_router(roles.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.cookies.get("access_token"):
        origin = request.headers.get("origin")
        if origin:
            expected_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
            if origin.rstrip("/") != expected_origin.rstrip("/"):
                return JSONResponse(status_code=403, content={"detail": "Cross-origin request blocked"})
    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
    started = time.monotonic()
    response = await call_next(request)
    logger.info("request_id=%s method=%s path=%s status=%s duration_ms=%.2f", request_id, request.method, request.url.path, response.status_code, (time.monotonic() - started) * 1000)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'"
    return response


@app.get("/health/live", include_in_schema=False)
async def health_live():
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
async def health_ready(db: db_dependency):
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


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

    def decimal_value(value):
        try:
            amount = Decimal(str(value or "0"))
            return amount if amount.is_finite() else Decimal("0")
        except (InvalidOperation, ValueError):
            return Decimal("0")

    def record_date(value):
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).date()
        except (TypeError, ValueError):
            try:
                return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
            except ValueError:
                return None

    date_to_text = request.query_params.get("date_to")
    date_from_text = request.query_params.get("date_from")
    today = datetime.now(timezone.utc).date()
    try:
        date_to = datetime.strptime(date_to_text, "%Y-%m-%d").date() if date_to_text else today
    except ValueError:
        date_to = today
    try:
        date_from = datetime.strptime(date_from_text, "%Y-%m-%d").date() if date_from_text else date_to - timedelta(days=29)
    except ValueError:
        date_from = date_to - timedelta(days=29)
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    def in_range(record):
        created = record_date(record.created_at)
        return created is not None and date_from <= created <= date_to

    invoices = [invoice for invoice in db.query(Invoices).all() if in_range(invoice)]
    payments = [payment for payment in db.query(Payments).filter(Payments.status == "completed").all() if in_range(payment)]
    purchases = [purchase for purchase in db.query(Purchases).all() if in_range(purchase)]
    supplier_payments = [payment for payment in db.query(SupplierPayments).all() if in_range(payment)]

    paid_by_invoice = {}
    for payment in payments:
        paid_by_invoice[payment.invoice_id] = (
            paid_by_invoice.get(payment.invoice_id, Decimal("0"))
            + decimal_value(payment.amount)
        )
    total_sales = sum((decimal_value(invoice.total_price) for invoice in invoices), Decimal("0"))
    sales_paid = sum(
        (min(paid_by_invoice.get(invoice.id, Decimal("0")), decimal_value(invoice.total_price)) for invoice in invoices),
        Decimal("0"),
    )
    invoice_due = max(total_sales - sales_paid, Decimal("0"))

    total_purchases = sum((decimal_value(purchase.total_amount) for purchase in purchases), Decimal("0"))
    purchases_paid = sum((decimal_value(payment.amount) for payment in supplier_payments), Decimal("0"))
    purchase_due = max(total_purchases - purchases_paid, Decimal("0"))

    sales_by_day = {}
    current = date_from
    while current <= date_to:
        sales_by_day[current.isoformat()] = Decimal("0")
        current += timedelta(days=1)
    for invoice in invoices:
        day = record_date(invoice.created_at)
        if day is not None:
            sales_by_day[day.isoformat()] += decimal_value(invoice.total_price)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "metrics": {
                "total_sales": total_sales,
                "net_sales": sales_paid,
                "invoice_due": invoice_due,
                "total_purchases": total_purchases,
                "purchase_due": purchase_due,
            },
            "sales_chart": json.dumps([
                {"date": day, "total": float(total)}
                for day, total in sales_by_day.items()
            ]),
        },
    )
