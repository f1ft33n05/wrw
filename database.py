from datetime import datetime, timezone
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
import database_models
from database_models import User, Contact
from typing import Annotated
from fastapi import Depends


db_url = "postgresql://postgres:bstar1234@localhost:5432/wrw_db"

engine = create_engine(db_url)

session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

install_date = datetime.now(timezone.utc)

seed_data = [
    User(name="Admin", username="admin", password="$2b$12$nkfCnkzJOc3eBWekSr/dAO1di/aJvFVOdGQBbm2if.hmeZNpTOvue", email="f1ft33n05@gmail.com", phone="1234567890", role="admin", created_at=install_date, updated_at=install_date),
    Contact(name="Walkin Customer", email="walkincustomer@wrw.com", phone="0987654321", contact_type="customer", address="Area 1, Lilongwe.", outstanding_balance=0, created_at=install_date, updated_at=install_date)
]

def get_db():
    db = session()
    try:
        yield db
    finally:
        db.close()
        
db_dependency = Annotated[Session, Depends(get_db)]

def ensure_sales_item_column(database_engine: Engine) -> None:
    inspector = inspect(database_engine)
    if inspector.has_table("sales_txns"):
        columns = {column["name"] for column in inspector.get_columns("sales_txns")}
        if "item_id" not in columns:
            with database_engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE sales_txns ADD COLUMN item_id INTEGER")
                )


def init_db():
    ensure_sales_item_column(engine)
    db = session()
    count = db.query(database_models.User).count()
    if count == 0:
        for item in seed_data:
            db.add(item)
        db.commit()
    db.close()