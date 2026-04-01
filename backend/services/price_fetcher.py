import os, requests
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from models.price import MandiPrice
from services.db import SessionLocal

DATA_GOV_API_KEY     = os.getenv("DATA_GOV_API_KEY")
DATA_GOV_RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
DATA_GOV_BASE_URL    = "https://api.data.gov.in/resource"

# All commodities to fetch daily
COMMODITIES = [
    "Tomato", "Onion", "Potato", "Brinjal", "Cabbage",
    "Cauliflower", "Beans", "Pumpkin", "Carrot", "Garlic",
    "Ginger", "Green Chilli", "Wheat", "Rice", "Maize",
    "Soyabean", "Groundnut", "Mustard", "Cotton", "Sugarcane"
]

def fetch_and_store(commodity: str, db: Session) -> int:
    """
    Fetch today's prices for one commodity from data.gov.in
    and upsert into PostgreSQL. Returns count of records stored.
    """
    params = {
        "api-key":            DATA_GOV_API_KEY,
        "format":             "json",
        "limit":              "500",
        "filters[commodity]": commodity,
    }
    url      = f"{DATA_GOV_BASE_URL}/{DATA_GOV_RESOURCE_ID}"
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()

    records = response.json().get("records", [])
    count   = 0

    for r in records:
        try:
            # Parse arrival date
            raw_date     = r.get("arrival_date", "")
            arrival_date = datetime.strptime(raw_date, "%d/%m/%Y").date()

            # Check if record already exists (SQLite compatible)
            existing = db.query(MandiPrice).filter(
                MandiPrice.market == r.get("market", "").strip(),
                MandiPrice.commodity == r.get("commodity", "").strip(),
                MandiPrice.variety == r.get("variety", "").strip(),
                MandiPrice.arrival_date == arrival_date
            ).first()

            if not existing:
                new_price = MandiPrice(
                    state        = r.get("state", "").strip(),
                    district     = r.get("district", "").strip(),
                    market       = r.get("market", "").strip(),
                    commodity    = r.get("commodity", "").strip(),
                    variety      = r.get("variety", "").strip(),
                    min_price    = float(r.get("min_price", 0) or 0),
                    max_price    = float(r.get("max_price", 0) or 0),
                    modal_price  = float(r.get("modal_price", 0) or 0),
                    arrival_date = arrival_date,
                    fetched_at   = datetime.utcnow(),
                )
                db.add(new_price)
                count += 1

        except Exception as e:
            print(f"Skipping record: {e}")
            continue

    db.commit()
    return count


def run_daily_fetch():
    """
    Fetches prices for ALL commodities and stores in DB.
    Called by APScheduler every day at midnight.
    Can also be triggered manually via /market/fetch endpoint.
    """
    db    = SessionLocal()
    total = 0
    print(f"[{datetime.utcnow()}] Starting daily price fetch...")

    for commodity in COMMODITIES:
        try:
            count  = fetch_and_store(commodity, db)
            total += count
            print(f"  {commodity}: {count} records stored")
        except Exception as e:
            print(f"  {commodity}: FAILED — {e}")
        finally:
            pass

    db.close()
    print(f"[{datetime.utcnow()}] Daily fetch complete. Total: {total} records.")
    return total