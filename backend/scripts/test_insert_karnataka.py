import os
import sys
from datetime import datetime, date

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy.dialects.postgresql import insert
from models.price import MandiPrice
from services.db import SessionLocal

db = SessionLocal()

row = {
    "state": "Karnataka",
    "district": "Bangalore",
    "market": "Bangalore",
    "commodity": "Onion",
    "variety": "Local-Test",
    "min_price": 600,
    "max_price": 1000,
    "modal_price": 800,
    "arrival_date": date.today(),
    "fetched_at": datetime.utcnow(),
}

stmt = insert(MandiPrice).values(**row).on_conflict_do_nothing(
    constraint="uq_market_commodity_date"
)

db.execute(stmt)
db.commit()
db.close()

print("Inserted test row")