# backend/agent/tools.py
import os
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import and_, func, or_, select

from backend.db.models import MandiPrice

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Load data files
ROOT = Path(__file__).parent.parent.parent
DISEASE_DB = (
    json.loads((ROOT / "backend" / "data" / "disease_db.json").read_text())
    if (ROOT / "backend" / "data" / "disease_db.json").exists()
    else {}
)
PROGRESSION_DB = (
    json.loads((ROOT / "backend" / "data" / "progression_db.json").read_text())
    if (ROOT / "backend" / "data" / "progression_db.json").exists()
    else {}
)
MANDI_COORDS = (
    json.loads((ROOT / "backend" / "data" / "mandi_coordinates.json").read_text())
    if (ROOT / "backend" / "data" / "mandi_coordinates.json").exists()
    else {}
)

print(f"Tools loaded: {len(DISEASE_DB)} diseases, {len(MANDI_COORDS)} mandis")

MANDI_PRICE_CACHE_TTL = 600
mandi_price_cache = {}


class tool:
    def __init__(self, func):
        self.func = func
        self.name = func.__name__
        self.__doc__ = func.__doc__

    def run(self, arg: str) -> str:
        return self.func(arg)

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


def _normalize_location_term(value: str) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    return value or None


def _extract_location_terms(location: str) -> list[str]:
    if not location:
        return []

    terms = []
    for part in location.split(","):
        term = _normalize_location_term(part)
        if term and term not in terms:
            terms.append(term)

    compact = _normalize_location_term(location)
    if compact and compact not in terms:
        terms.append(compact)

    return terms


def _format_mandi_rows(rows, crop: str, location: str) -> str:
    if not rows:
        if location:
            return f"Price data not available for {crop} near {location}"
        return f"Price data not available for {crop}"

    parts = [f"Mandi Prices for {crop}:"]
    for row in rows:
        parts.append(
            "\n".join(
                [
                    f"Market: {row.market}",
                    f"Min: Rs.{row.min_price}",
                    f"Max: Rs.{row.max_price}",
                    f"Modal: Rs.{row.modal_price}",
                ]
            )
        )
    return "\n---\n".join(parts)


def _serialize_mandi_rows(rows) -> list[dict]:
    return [
        {
            "market": row.market,
            "min": row.min_price,
            "max": row.max_price,
            "modal": row.modal_price,
        }
        for row in rows
    ]


def format_mandi_data(mandi_payload: dict) -> str:
    crop = mandi_payload.get("crop")
    location = mandi_payload.get("location")
    markets = mandi_payload.get("markets", [])

    if not markets:
        if location:
            return f"Price data not available for {crop} near {location}"
        return f"Price data not available for {crop}"

    parts = [f"Mandi Prices for {crop}:"]
    for item in markets:
        parts.append(
            "\n".join(
                [
                    f"Market: {item['market']}",
                    f"Min: Rs.{item['min']}",
                    f"Max: Rs.{item['max']}",
                    f"Modal: Rs.{item['modal']}",
                ]
            )
        )
    return "\n---\n".join(parts)


def _build_latest_mandi_query(crop: str, location_terms: list[str], match_field: str | None):
    filters = [func.lower(MandiPrice.commodity) == crop]
    if match_field == "district" and location_terms:
        filters.append(
            or_(*[MandiPrice.district.ilike(f"%{term}%") for term in location_terms])
        )
    elif match_field == "state" and location_terms:
        filters.append(
            or_(*[MandiPrice.state.ilike(f"%{term}%") for term in location_terms])
        )

    latest_dates = (
        select(
            MandiPrice.market.label("market"),
            func.max(MandiPrice.arrival_date).label("latest_date"),
        )
        .where(*filters)
        .group_by(MandiPrice.market)
        .subquery()
    )

    return (
        select(MandiPrice)
        .join(
            latest_dates,
            and_(
                MandiPrice.market == latest_dates.c.market,
                MandiPrice.arrival_date == latest_dates.c.latest_date,
            ),
        )
        .where(*filters)
        .order_by(MandiPrice.arrival_date.desc(), MandiPrice.market.asc())
    )


async def get_mandi_price_data_from_db(db, crop: str, location: str) -> dict:
    crop = _normalize_location_term(crop)
    location = _normalize_location_term(location)

    if not crop:
        return {"crop": crop, "location": location or "", "markets": []}

    cache_key = (crop, location or "")
    cached = mandi_price_cache.get(cache_key)
    if cached:
        cached_value, cached_at = cached
        if time.time() - cached_at < MANDI_PRICE_CACHE_TTL:
            return cached_value

    location_terms = _extract_location_terms(location or "")

    district_query = (
        _build_latest_mandi_query(crop, location_terms, "district")
        if location_terms
        else None
    )
    state_query = (
        _build_latest_mandi_query(crop, location_terms, "state")
        if location_terms
        else None
    )
    fallback_query = _build_latest_mandi_query(crop, [], None)

    rows = []
    if district_query is not None:
        rows = (await db.execute(district_query)).scalars().all()

    if not rows and state_query is not None:
        rows = (await db.execute(state_query)).scalars().all()

    if not rows:
        rows = (await db.execute(fallback_query)).scalars().all()

    print("📊 TOTAL ROWS FROM DB:", len(rows))

    mandi_payload = {
        "crop": crop,
        "location": location or "",
        "markets": _serialize_mandi_rows(rows),
    }
    mandi_price_cache[cache_key] = (mandi_payload, time.time())
    if len(mandi_price_cache) > 200:
        mandi_price_cache.clear()
    return mandi_payload


async def get_mandi_price_data_from_db(db, crop: str, location: str) -> dict:
    crop = _normalize_location_term(crop)
    location = _normalize_location_term(location)

    if not crop:
        return {"crop": crop, "location": location or "", "markets": [], "source": "none"}

    cache_key = (crop, location or "")
    cached = mandi_price_cache.get(cache_key)
    if cached:
        cached_value, cached_at = cached
        if time.time() - cached_at < MANDI_PRICE_CACHE_TTL:
            return cached_value

    location_terms = _extract_location_terms(location or "")

    # Level 1: District/City exact match
    if location_terms:
        district_query = _build_latest_mandi_query(crop, location_terms, "district")
        rows = (await db.execute(district_query)).scalars().all()

        if rows:
            print(f"Level 1 match: {len(rows)} markets in district")
            result = _build_result(crop, location, rows, "district_match")
            _cache_result(cache_key, result)
            return result

    # Level 2: State match
    if location_terms:
        state_query = _build_latest_mandi_query(crop, location_terms, "state")
        rows = (await db.execute(state_query)).scalars().all()

        if rows:
            print(f"Level 2 match: {len(rows)} markets in state")
            result = _build_result(crop, location, rows, "state_match")
            _cache_result(cache_key, result)
            return result

    # Level 3: All India best prices
    fallback_query = _build_latest_mandi_query(crop, [], None)
    rows = (await db.execute(fallback_query)).scalars().all()

    if rows:
        print(f"Level 3 match: {len(rows)} markets nationally")
        result = _build_result(crop, location, rows, "national")
        _cache_result(cache_key, result)
        return result

    # Level 4: Agmarknet API
    print("No DB data -> trying Agmarknet API")
    api_result = _fetch_agmarknet(crop)
    if api_result:
        result = {
            "crop": crop,
            "location": location or "",
            "markets": api_result,
            "source": "agmarknet_api",
        }
        _cache_result(cache_key, result)
        return result

    # Level 5: Empty -> LLM will handle
    print(f"No data anywhere for {crop}")
    return {
        "crop": crop,
        "location": location or "",
        "markets": [],
        "source": "none",
    }


def _build_result(crop, location, rows, source) -> dict:
    return {
        "crop": crop,
        "location": location or "",
        "markets": _serialize_mandi_rows(rows),
        "source": source,
    }


def _cache_result(cache_key, result):
    mandi_price_cache[cache_key] = (result, time.time())
    if len(mandi_price_cache) > 200:
        mandi_price_cache.clear()


def _fetch_agmarknet(crop: str) -> list:
    """Fetch live prices from Agmarknet government API"""
    try:
        key = os.getenv("AGMARKNET_API_KEY")
        if not key:
            return []

        res = requests.get(
            "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070",
            params={
                "api-key": key,
                "format": "json",
                "limit": 10,
                "filters[Commodity]": crop.capitalize(),
            },
            timeout=5,
        ).json()

        records = res.get("records", [])
        if not records:
            return []

        return [
            {
                "market": r.get("Market", "Unknown"),
                "min": float(r.get("Min Price", 0)),
                "max": float(r.get("Max Price", 0)),
                "modal": float(r.get("Modal Price", 0)),
                "min_price": float(r.get("Min Price", 0)),
                "max_price": float(r.get("Max Price", 0)),
                "modal_price": float(r.get("Modal Price", 0)),
            }
            for r in records
        ]
    except Exception as e:
        print(f"Agmarknet API error: {e}")
        return []

async def get_mandi_price_from_db(db, crop: str, location: str) -> str:
    mandi_payload = await get_mandi_price_data_from_db(db, crop, location)
    return format_mandi_data(mandi_payload)


@tool
def get_weather(location: str) -> str:
    """Get current weather and disease risk for a farm location."""
    try:
        key = os.getenv("OPENWEATHER_API_KEY")
        res = requests.get(
            "http://api.openweathermap.org/data/2.5/weather",
            params={"q": location, "appid": key, "units": "metric"},
            timeout=5,
        ).json()
        temp = res["main"]["temp"]
        humidity = res["main"]["humidity"]
        desc = res["weather"][0]["description"]
        if humidity > 80 and 20 <= temp <= 30:
            risk = "HIGH fungal risk — avoid spraying today"
        elif humidity > 60:
            risk = "MEDIUM risk — monitor closely"
        else:
            risk = "LOW risk — good conditions for spraying"
        return (
            f"Weather in {location}:\n"
            f"Temperature : {temp}°C\n"
            f"Humidity    : {humidity}%\n"
            f"Condition   : {desc}\n"
            f"Disease Risk: {risk}"
        )
    except Exception as e:
        return f"Could not fetch weather for {location}"


@tool
def get_mandi_price(crop: str) -> str:
    """Compatibility wrapper for mandi prices."""
    return f"Mandi price lookup now requires a database session for {crop}"


@tool
def get_treatment(disease: str) -> str:
    """Get detailed treatment for a crop disease."""
    disease_lower = disease.lower()
    match = None

    # Try multiple matching strategies
    for key, val in DISEASE_DB.items():
        key_lower = key.lower()
        # Strategy 1 — exact contains
        if disease_lower in key_lower or key_lower in disease_lower:
            match = val
            break
        # Strategy 2 — word by word match
        disease_words = set(disease_lower.split())
        key_words = set(key_lower.split())
        if len(disease_words & key_words) >= 2:
            match = val
            break

    if match:
        remedies = match.get("remedies", {})
        organic = remedies.get("organic", [])[:3]
        chemical = remedies.get("chemical", [])[:2]
        urgency = match.get("urgency", "")
        result = f"Treatment for {match.get('display_name', disease)}:\n\n"
        if organic:
            result += "Organic:\n"
            for r in organic:
                result += f"  • {r}\n"
        if chemical:
            result += "\nChemical:\n"
            for r in chemical:
                result += f"  • {r}\n"
        result += f"\nUrgency: {urgency}"
        return result

    return (
        f"No specific treatment found. Consult local agriculture officer for {disease}"
    )


@tool
def get_disease_progression(disease: str) -> str:
    """Get how fast a disease spreads if left untreated."""
    disease_lower = disease.lower()
    for key, val in PROGRESSION_DB.items():
        if disease_lower in key.lower() or key.lower() in disease_lower:
            rate = val.get("daily_spread_rate", 0)
            note = val.get("untreated_note", "")
            day7 = min(100, rate * 7 * 100)
            return (
                f"Disease Spread Prediction:\n"
                f"Daily spread rate: {rate * 100:.0f}%\n"
                f"If untreated for 7 days: {day7:.0f}% of crop affected\n"
                f"Warning: {note}"
            )
    return f"Spread data not available for {disease}"


@tool
def get_nearby_mandis(location: str) -> str:
    """Find nearest mandis to farmer's location using coordinates."""
    location_lower = location.lower()
    found = []

    # Search by city name
    for mandi, coords in MANDI_COORDS.items():
        if (
            location_lower in mandi.lower()
            or location_lower in coords.get("state", "").lower()
        ):
            found.append(
                {
                    "name": mandi,
                    "state": coords["state"],
                    "lat": coords["lat"],
                    "lng": coords["lng"],
                }
            )

    if found:
        result = f"Mandis near {location}:\n"
        for m in found[:5]:
            result += f"  • {m['name']} ({m['state']})\n"
        return result

    # Try geocoding with OpenStreetMap (free!)
    try:
        res = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": f"{location}, India",
                "format": "json",
                "limit": 1,
                "countrycodes": "in",
            },
            headers={"User-Agent": "KrishiMitra/1.0"},
            timeout=5,
        ).json()

        if res:
            lat = float(res[0]["lat"])
            lng = float(res[0]["lon"])
            name = res[0]["display_name"].split(",")[0]
            return (
                f"Location found: {name}\n"
                f"Coordinates: {lat:.4f}, {lng:.4f}\n"
                f"Check local mandi for price details."
            )
    except:
        pass

    return f"Could not find mandis near {location}. Try a city or district name."


@tool
def get_govt_schemes(state: str) -> str:
    """Get government schemes available for farmers."""
    schemes = [
        {
            "name": "PM Fasal Bima Yojana",
            "benefit": "Crop insurance against losses",
            "how": "Visit nearest bank or CSC center",
        },
        {
            "name": "PM Kisan Samman Nidhi",
            "benefit": "Rs.6000/year direct to bank",
            "how": "Register at pmkisan.gov.in",
        },
        {
            "name": "Kisan Credit Card",
            "benefit": "Low interest crop loans",
            "how": "Apply at any nationalized bank",
        },
        {
            "name": "Soil Health Card",
            "benefit": "Free soil testing + recommendations",
            "how": "Contact local agriculture office",
        },
    ]
    result = f"Government schemes for farmers in {state}:\n\n"
    for s in schemes:
        result += (
            f"Scheme : {s['name']}\nBenefit: {s['benefit']}\nHow    : {s['how']}\n---\n"
        )
    return result

