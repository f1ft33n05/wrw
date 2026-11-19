from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette import status

from database import db_dependency
from database_models import SystemSetting
from models import Role
from routes.auth import RoleChecker, get_current_user


router = APIRouter(prefix="/settings", tags=["settings"])
templates = Jinja2Templates(directory="templates")
user_dependency = Annotated[dict, Depends(get_current_user)]
SETTINGS_ACCESS = Depends(RoleChecker(Role.admin, module="settings"))

DEFAULTS = {
    "receipt_prefix": "RCT",
    "quotation_prefix": "QT",
    "invoice_prefix": "INV",
    "document_layout": "standard",
    "document_footer": "",
}


def get_settings(db):
    values = db.query(SystemSetting).all()
    settings = {setting.key: setting.value for setting in values}
    fixed_prefixes = {"receipt_prefix", "quotation_prefix", "invoice_prefix"}
    return {
        key: value if key in fixed_prefixes else settings.get(key, value)
        for key, value in DEFAULTS.items()
    }


@router.get("", response_class=HTMLResponse, dependencies=[SETTINGS_ACCESS])
@router.get("/", response_class=HTMLResponse, dependencies=[SETTINGS_ACCESS])
async def settings_page(request: Request, user: user_dependency, db: db_dependency):
    return templates.TemplateResponse(request, "settings.html", {"user": user, "settings": get_settings(db)})


@router.post("", dependencies=[SETTINGS_ACCESS])
@router.post("/", dependencies=[SETTINGS_ACCESS])
async def update_settings(
    db: db_dependency,
    document_layout: str = Form(...),
    document_footer: str = Form(default=""),
):
    values = {
        "document_layout": document_layout.strip(),
        "document_footer": document_footer.strip(),
    }
    existing = {setting.key: setting for setting in db.query(SystemSetting).all()}
    for key, value in values.items():
        if key in existing:
            existing[key].value = value
        else:
            db.add(SystemSetting(key=key, value=value))
    db.commit()
    return RedirectResponse(url="/settings?updated=1", status_code=status.HTTP_303_SEE_OTHER)
