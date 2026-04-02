# services/price_fetcher.py

import os
import re
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from models.price import MandiPrice
from services.db import SessionLocal
from services.market_service import karnataka_rows_exist

DATA_GOV_API_KEY = os.getenv("DATA_GOV_API_KEY")
DATA_GOV_RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
DATA_GOV_BASE_URL = "https://api.data.gov.in/resource"

COMMODITIES = [
    "Tomato", "Onion", "Potato", "Brinjal", "Cabbage",
    "Cauliflower", "Beans", "Pumpkin", "Carrot", "Garlic",
    "Ginger", "Green Chilli", "Wheat", "Rice", "Maize",
    "Soyabean", "Groundnut", "Mustard", "Cotton", "Sugarcane"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def _safe_float(value):
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return 0.0


def _parse_date(raw_date: str):
    if not raw_date:
        return datetime.utcnow().date()

    raw_date = raw_date.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw_date, fmt).date()
        except ValueError:
            continue

    return datetime.utcnow().date()


def upsert_record(db: Session, row: dict):
    stmt = insert(MandiPrice).values(
        state=row.get("state", "").strip(),
        district=row.get("district", "").strip(),
        market=row.get("market", "").strip(),
        commodity=row.get("commodity", "").strip(),
        variety=row.get("variety", "").strip(),
        min_price=_safe_float(row.get("min_price", 0)),
        max_price=_safe_float(row.get("max_price", 0)),
        modal_price=_safe_float(row.get("modal_price", 0)),
        arrival_date=_parse_date(str(row.get("arrival_date", ""))),
        fetched_at=datetime.utcnow(),
    ).on_conflict_do_nothing(
        constraint="uq_market_commodity_date"
    )

    db.execute(stmt)


def fetch_and_store(commodity: str, db: Session) -> int:
    """
    Official source fetch from data.gov.in
    """
    params = {
        "api-key": DATA_GOV_API_KEY,
        "format": "json",
        "limit": "500",
        "filters[commodity]": commodity,
    }
    url = f"{DATA_GOV_BASE_URL}/{DATA_GOV_RESOURCE_ID}"
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    records = response.json().get("records", [])
    count = 0

    for r in records:
        try:
            row = {
                "state": r.get("state", ""),
                "district": r.get("district", ""),
                "market": r.get("market", ""),
                "commodity": r.get("commodity", ""),
                "variety": r.get("variety", "") or "General",
                "min_price": r.get("min_price", 0),
                "max_price": r.get("max_price", 0),
                "modal_price": r.get("modal_price", 0),
                "arrival_date": r.get("arrival_date", ""),
            }
            upsert_record(db, row)
            count += 1
        except Exception as e:
            print(f"[data.gov] Skipping record for {commodity}: {e}")
            continue

    db.commit()
    return count


def scrape_napanta_karnataka(commodity: str, db: Session) -> int:
    """
    Temporary Karnataka fallback.
    Adjust URL/selectors after testing the exact page you want.
    """
    # Replace this with an exact NaPanta page you test in browser.
    url = "https://www.napanta.com/market-price/karnataka"

    response = requests.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        print(f"[napanta] No tables found for {commodity}")
        return 0

    inserted = 0

    for table in tables:
        for tr in table.find_all("tr"):
            cols = [td.get_text(" ", strip=True) for td in tr.find_all("td")]

            # adjust if the real page has different number/order
            if len(cols) < 6:
                continue

            market = cols[0].strip()
            scraped_commodity = cols[1].strip()
            variety = cols[2].strip() or "General"
            min_price = _safe_float(cols[3])
            max_price = _safe_float(cols[4])
            modal_price = _safe_float(cols[5])
            arrival_date = cols[6].strip() if len(cols) > 6 else datetime.utcnow().date()

            if scraped_commodity.lower() != commodity.lower():
                continue

            row = {
                "state": "Karnataka",
                "district": "Unknown",
                "market": market,
                "commodity": scraped_commodity,
                "variety": variety,
                "min_price": min_price,
                "max_price": max_price,
                "modal_price": modal_price,
                "arrival_date": arrival_date,
            }

            try:
                upsert_record(db, row)
                inserted += 1
            except Exception as e:
                print(f"[napanta] Skip {commodity}: {e}")

    db.commit()
    time.sleep(1)
    return inserted


def fetch_with_fallback(commodity: str, db: Session) -> dict:
    """
    1. Try official API
    2. If Karnataka rows are still missing, scrape fallback and store
    """
    official_count = 0
    fallback_count = 0

    try:
        official_count = fetch_and_store(commodity, db)
    except Exception as e:
        print(f"[official] {commodity} failed: {e}")

    if not karnataka_rows_exist(commodity, db):
        try:
            fallback_count = scrape_napanta_karnataka(commodity, db)
        except Exception as e:
            print(f"[fallback] {commodity} failed: {e}")

    return {
        "commodity": commodity,
        "official_count": official_count,
        "fallback_count": fallback_count,
        "total_added": official_count + fallback_count,
    }


def run_daily_fetch():
    """
    Fetch all commodities from official API,
    then fill Karnataka gaps using fallback scraper.
    """
    db = SessionLocal()
    total = 0
    details = []

    print(f"[{datetime.utcnow()}] Starting mandi fetch...")

    try:
        for commodity in COMMODITIES:
            result = fetch_with_fallback(commodity, db)
            total += result["total_added"]
            details.append(result)
            print(
                f"{commodity}: official={result['official_count']} "
                f"fallback={result['fallback_count']} "
                f"total={result['total_added']}"
            )
    finally:
        db.close()

    print(f"[{datetime.utcnow()}] Fetch complete. Total inserted: {total}")
    return {
        "total": total,
        "details": details
    }