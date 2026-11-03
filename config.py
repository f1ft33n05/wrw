import os

from dotenv import load_dotenv
from zoneinfo import ZoneInfo


load_dotenv()

_timezone_name = os.getenv("APP_TIMEZONE", "Africa/Harare").strip()
if _timezone_name.startswith("ZoneInfo(") and _timezone_name.endswith(")"):
    _timezone_name = _timezone_name[len("ZoneInfo("):-1].strip("'\"")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/wrw_db")
SECRET_KEY = os.getenv("SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "20"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
APP_TIMEZONE = ZoneInfo(_timezone_name)
CURRENCY_CODE = os.getenv("CURRENCY_CODE", "MWK")

ADMIN_NAME = os.getenv("ADMIN_NAME", "Admin")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "")

DEFAULT_CUSTOMER_NAME = os.getenv("DEFAULT_CUSTOMER_NAME", "Walk-in Customer")
DEFAULT_CUSTOMER_EMAIL = os.getenv("DEFAULT_CUSTOMER_EMAIL", "walkincustomer@example.com")
DEFAULT_CUSTOMER_PHONE = os.getenv("DEFAULT_CUSTOMER_PHONE", "")
DEFAULT_CUSTOMER_ADDRESS = os.getenv("DEFAULT_CUSTOMER_ADDRESS", "")

if ENVIRONMENT == "production":
    if len(SECRET_KEY.encode("utf-8")) < 32:
        raise RuntimeError("SECRET_KEY must contain at least 32 bytes in production")
    if not ADMIN_PASSWORD:
        raise RuntimeError("ADMIN_PASSWORD is required in production")
    if ADMIN_PASSWORD and len(ADMIN_PASSWORD) < 12:
        raise RuntimeError("ADMIN_PASSWORD must contain at least 12 characters in production")
