from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from fastapi import HTTPException
from starlette import status


CENT = Decimal("0.01")


def decimal_value(value: object, description: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {description}",
        ) from None
    if not result.is_finite():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {description}",
        )
    return result


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def format_money(value: object) -> str:
    return f"MWK {money(decimal_value(value, 'money amount')):,.2f}"


def format_compact(value: object, description: str) -> str:
    return format(decimal_value(value, description).normalize(), ",f")


def validate_payment_method(value: str) -> str:
    method = value.strip().lower()
    if method not in {"cash", "card", "mobile money", "bank transfer"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported payment method",
        )
    return method
