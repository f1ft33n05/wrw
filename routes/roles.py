import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette import status

from database import db_dependency
from database_models import RoleDefinition, RolePermission, User
from models import Role
from routes.auth import RoleChecker, get_current_user


router = APIRouter(prefix="/roles", tags=["roles"])
templates = Jinja2Templates(directory="templates")
user_dependency = Annotated[dict, Depends(get_current_user)]
ROLE_ACCESS = Depends(RoleChecker(Role.admin, module="users"))
ROLE_CREATE_ACCESS = Depends(RoleChecker(Role.admin, module="users", action="can_create"))
ROLE_EDIT_ACCESS = Depends(RoleChecker(Role.admin, module="users", action="can_edit"))
ROLE_DELETE_ACCESS = Depends(RoleChecker(Role.admin, module="users", action="can_delete"))

MODULES = [
    ("dashboard", "Dashboard"),
    ("users", "Users & roles"),
    ("contacts", "Contacts"),
    ("items", "Items & inventory"),
    ("sales", "Sales & POS"),
    ("events", "Events"),
    ("quotations", "Quotations"),
    ("invoices", "Invoices"),
    ("purchases", "Purchases"),
    ("reports", "Reports"),
    ("inventory", "Inventory"),
]


class RolePayload(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    description: str = ""
    permissions: dict[str, dict[str, bool]] = {}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def normalize_permissions(payload: RolePayload):
    known = {key for key, _ in MODULES}
    selected = {}
    for module, actions in payload.permissions.items():
        if module in known:
            selected[module] = {
                "can_view": 1 if actions.get("can_view") else 0,
                "can_create": 1 if actions.get("can_create") else 0,
                "can_edit": 1 if actions.get("can_edit") else 0,
                "can_delete": 1 if actions.get("can_delete") else 0,
            }
    return selected


@router.get("", response_class=HTMLResponse, dependencies=[ROLE_ACCESS])
@router.get("/", response_class=HTMLResponse, dependencies=[ROLE_ACCESS])
async def roles_page(request: Request, user: user_dependency, db: db_dependency):
    roles = db.query(RoleDefinition).order_by(RoleDefinition.name).all()
    permissions = db.query(RolePermission).order_by(RolePermission.role_name, RolePermission.module).all()
    permissions_by_role = {}
    for permission in permissions:
        permissions_by_role.setdefault(permission.role_name, {})[permission.module] = permission
    permissions_json = {}
    for role_name, role_permissions in permissions_by_role.items():
        permissions_json[role_name] = {
            module: {
                "can_view": permission.can_view,
                "can_create": permission.can_create,
                "can_edit": permission.can_edit,
                "can_delete": permission.can_delete,
            }
            for module, permission in role_permissions.items()
        }
    role_user_counts = {
        role.name: db.query(User).filter(User.role == role.name).count()
        for role in roles
    }
    return templates.TemplateResponse(request, "roles.html", {
        "user": user,
        "roles": roles,
        "permissions_by_role": permissions_by_role,
        "modules": MODULES,
        "permissions_by_role_json": json.dumps(permissions_json),
        "role_user_counts": role_user_counts,
    })


@router.post("", status_code=201, dependencies=[ROLE_CREATE_ACCESS])
@router.post("/", status_code=201, dependencies=[ROLE_CREATE_ACCESS])
async def create_role(payload: RolePayload, db: db_dependency):
    name = payload.name.strip().lower()
    if name in {"", "admin"} or not name.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=422, detail="Enter a valid role name")
    if db.query(RoleDefinition).filter(RoleDefinition.name == name).first():
        raise HTTPException(status_code=409, detail="A role with this name already exists")

    now = timestamp()
    role = RoleDefinition(name=name, description=payload.description.strip(), system_role=0, created_at=now, updated_at=now)
    db.add(role)
    db.flush()
    for module, actions in normalize_permissions(payload).items():
        db.add(RolePermission(role_name=name, module=module, created_at=now, updated_at=now, **actions))
    db.commit()
    return {"message": "Role created", "name": name}


@router.put("/{role_id}", dependencies=[ROLE_EDIT_ACCESS])
async def update_role(role_id: int, payload: RolePayload, db: db_dependency):
    role = db.query(RoleDefinition).filter(RoleDefinition.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.system_role and payload.name.strip().lower() != role.name:
        raise HTTPException(status_code=409, detail="System role names cannot be changed")

    name = payload.name.strip().lower()
    existing = db.query(RoleDefinition).filter(RoleDefinition.name == name, RoleDefinition.id != role_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="A role with this name already exists")

    old_name = role.name
    if old_name != name:
        if db.query(User).filter(User.role == old_name).first():
            raise HTTPException(status_code=409, detail="Rename a role only after moving assigned users")
        for permission in db.query(RolePermission).filter(RolePermission.role_name == old_name).all():
            db.delete(permission)
    role.name = name
    role.description = payload.description.strip()
    role.updated_at = timestamp()

    existing_permissions = db.query(RolePermission).filter(RolePermission.role_name == name).all()
    by_module = {permission.module: permission for permission in existing_permissions}
    now = timestamp()
    for module, actions in normalize_permissions(payload).items():
        permission = by_module.get(module)
        if permission is None:
            permission = RolePermission(role_name=name, module=module, created_at=now, updated_at=now)
            db.add(permission)
        for field, value in actions.items():
            setattr(permission, field, value)
        permission.updated_at = now
    for module, permission in by_module.items():
        if module not in normalize_permissions(payload):
            db.delete(permission)
    db.commit()
    return {"message": "Role updated", "name": name}


@router.delete("/{role_id}", status_code=204, dependencies=[ROLE_DELETE_ACCESS])
async def delete_role(role_id: int, db: db_dependency):
    role = db.query(RoleDefinition).filter(RoleDefinition.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.system_role:
        raise HTTPException(status_code=409, detail="System roles cannot be deleted")
    if db.query(User).filter(User.role == role.name).first():
        raise HTTPException(status_code=409, detail="Move assigned users before deleting this role")
    db.query(RolePermission).filter(RolePermission.role_name == role.name).delete(synchronize_session=False)
    db.delete(role)
    db.commit()
