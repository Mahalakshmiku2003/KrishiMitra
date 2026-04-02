"""
scripts/build_mandi_coordinates.py

Geocodes Karnataka mandis from DB using Nominatim.
Handles messy market names with 3-level fallback:
  1. Full name: "Binny Mill (F&V), Bangalore, Karnataka"
  2. District only: "Bangalore, Karnataka"  <- saves district coords if market not found
  3. Skip if both fail
"""

import os
import sys
import json
import time
import re
import requests

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.db import SessionLocal
from sqlalchemy import text

OUTPUT_FILE = os.path.join(BACKEND_DIR, "data", "mandi_coordinates.json")
HEADERS = {"User-Agent": "KrishiMitra/1.0"}


def clean_market_name(name: str) -> str:
    """Remove bracketed suffixes like (F&V), (Uzhavar Sandhai), APMC etc."""
    name = re.sub(r"\(.*?\)", "", name)  # remove anything in brackets
    name = re.sub(r"\bAPMC\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def geocode(query: str) -> dict | None:
    url = "https://nominatim.openstreetmap.org/search"
    try:
        resp = requests.get(
            url,
            params={"q": query, "format": "json", "limit": 1},
            headers=HEADERS,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            return {
                "lat": float(data[0]["lat"]),
                "lng": float(data[0]["lon"]),
                "resolved_address": data[0]["display_name"],
            }
    except Exception as e:
        print(f"    Geocode error: {e}")
    return None


def fetch_unique_markets():
    db = SessionLocal()
    try:
        result = db.execute(
            text("""
            SELECT DISTINCT state, district, market
            FROM mandi_prices
            WHERE market IS NOT NULL
              AND district IS NOT NULL
              AND state IS NOT NULL
              AND LOWER(state) = 'karnataka'
            ORDER BY district, market
        """)
        )
        return [dict(row._mapping) for row in result.fetchall()]
    finally:
        db.close()


def build_coordinates():
    markets = fetch_unique_markets()
    print(f"Found {len(markets)} unique Karnataka markets\n")

    # Load existing to avoid re-geocoding
    existing = {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE) as f:
                for entry in json.load(f):
                    existing[entry["market"]] = entry
            print(f"Loaded {len(existing)} existing entries\n")
        except Exception:
            pass

    coordinates = []

    for i, row in enumerate(markets, start=1):
        market = row["market"].strip()
        district = row["district"].strip()
        state = row["state"].strip()

        # Already geocoded — keep it
        if market in existing:
            print(f"[{i}/{len(markets)}] Skipping (cached): {market}")
            coordinates.append(existing[market])
            continue

        clean = clean_market_name(market)

        # Attempt 1: cleaned market name + district
        query1 = f"{clean}, {district}, {state}, India"
        print(f"[{i}/{len(markets)}] Trying: {query1}")
        result = geocode(query1)
        time.sleep(1)

        # Attempt 2: district only (so we at least have approximate coords)
        if not result and clean.lower() != district.lower():
            query2 = f"{district}, {state}, India"
            print(f"           Fallback: {query2}")
            result = geocode(query2)
            time.sleep(1)

        if result:
            entry = {
                "market": market,
                "district": district,
                "state": state,
                "lat": result["lat"],
                "lng": result["lng"],
                "resolved_address": result["resolved_address"],
            }
            coordinates.append(entry)
            print(f"           ✅ {result['lat']}, {result['lng']}")
        else:
            print(f"           ❌ Skipped — no result")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(coordinates, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {len(coordinates)}/{len(markets)} market coordinates to:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    build_coordinates()
