import os
import sys
import json
import time
import requests
from sqlalchemy import text

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.db import SessionLocal

OUTPUT_FILE = os.path.join(BACKEND_DIR, "data", "mandi_coordinates.json")

HEADERS = {
    "User-Agent": "KrishiMitra/1.0"
}

def geocode_location(query: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1
    }

    response = requests.get(url, params=params, headers=HEADERS, timeout=20)
    response.raise_for_status()
    data = response.json()

    if not data:
        return None

    return {
        "lat": float(data[0]["lat"]),
        "lng": float(data[0]["lon"]),
        "display_name": data[0]["display_name"]
    }


def fetch_unique_markets():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT DISTINCT state, district, market
            FROM mandi_prices
            WHERE market IS NOT NULL
              AND district IS NOT NULL
              AND state IS NOT NULL
              AND LOWER(state) = 'karnataka'
            ORDER BY district, market
        """))
        return [dict(row._mapping) for row in result.fetchall()]
    finally:
        db.close()


def build_coordinates():
    unique_markets = fetch_unique_markets()
    print(f"Found {len(unique_markets)} unique Karnataka markets")

    coordinates = []

    for i, row in enumerate(unique_markets, start=1):
        market = row["market"].strip()
        district = row["district"].strip()
        state = row["state"].strip()

        query = f"{market}, {district}, {state}, India"
        print(f"[{i}/{len(unique_markets)}] Geocoding: {query}")

        try:
            result = geocode_location(query)
            if result:
                coordinates.append({
                    "market": market,
                    "district": district,
                    "state": state,
                    "lat": result["lat"],
                    "lng": result["lng"],
                    "resolved_address": result["display_name"]
                })
                print(f"  ✅ {result['lat']}, {result['lng']}")
            else:
                print("  ❌ No result")
        except Exception as e:
            print(f"  ❌ Failed: {e}")

        time.sleep(1)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(coordinates, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(coordinates)} market coordinates to:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    build_coordinates()