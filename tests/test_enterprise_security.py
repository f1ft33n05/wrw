import asyncio
from datetime import timedelta

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from models import SaleLineRequest
from pydantic import ValidationError
from config import APP_TIMEZONE
from routes.auth import create_access_token, get_current_user, safe_return_path


def test_sale_line_cannot_accept_manual_discount():
    line = SaleLineRequest.model_validate({
        "item_id": 1,
        "quantity": "2",
        "discount_percentage": "90",
    })
    assert not hasattr(line, "discount_percentage")


def test_sale_quantity_must_be_positive():
    try:
        SaleLineRequest(item_id=1, quantity="0")
    except ValidationError:
        return
    raise AssertionError("Zero quantity was accepted")


def test_application_timezone_is_configured():
    assert str(APP_TIMEZONE)


def test_login_return_path_accepts_local_paths():
    assert safe_return_path("/sales/pos?event_id=1") == "/sales/pos?event_id=1"


def test_login_return_path_rejects_external_redirects():
    assert safe_return_path("https://example.com") is None
    assert safe_return_path("//example.com") is None
    assert safe_return_path("/\\example.com") is None


def test_expired_cookie_token_has_session_expired_marker():
    token = create_access_token(
        "expired-user",
        1,
        "admin",
        expires_delta=timedelta(seconds=-1),
    )
    request = Request({
        "type": "http",
        "method": "GET",
        "scheme": "http",
        "path": "/dashboard",
        "query_string": b"",
        "headers": [(b"cookie", f"access_token={token}".encode())],
        "server": ("testserver", 80),
        "client": ("testclient", 1234),
        "root_path": "",
    })

    with pytest.raises(HTTPException) as error:
        asyncio.run(get_current_user(request, None, None))

    assert error.value.status_code == 401
    assert error.value.headers["X-Session-Expired"] == "true"
