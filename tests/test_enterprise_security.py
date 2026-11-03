from models import SaleLineRequest
from pydantic import ValidationError
from config import APP_TIMEZONE


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
