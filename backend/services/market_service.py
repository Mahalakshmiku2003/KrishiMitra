# services/market_service.py

import os
import json
from math import radians, sin, cos, sqrt, atan2
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from models.price import MandiPrice

TRANSPORT_COST_PER_KM = 2.5

COORDS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "mandi_coordinates.json"
)

STATE_COORDS = {
    "Andhra Pradesh":    {"lat": 15.9129, "lng": 79.7400},
    "Assam":             {"lat": 26.2006, "lng": 92.9376},
    "Bihar":             {"lat": 25.0961, "lng": 85.3131},
    "Chhattisgarh":      {"lat": 21.2787, "lng": 81.8661},
    "Delhi":             {"lat": 28.7041, "lng": 77.1025},
    "Goa":               {"lat": 15.2993, "lng": 74.1240},
    "Gujarat":           {"lat": 22.2587, "lng": 71.1924},
    "Haryana":           {"lat": 29.0588, "lng": 76.0856},
    "Himachal Pradesh":  {"lat": 31.1048, "lng": 77.1734},
    "Jharkhand":         {"lat": 23.6102, "lng": 85.2799},
    "Karnataka":         {"lat": 15.3173, "lng": 75.7139},
    "Kerala":            {"lat": 10.8505, "lng": 76.2711},
    "Madhya Pradesh":    {"lat": 22.9734, "lng": 78.6569},
    "Maharashtra":       {"lat": 19.7515, "lng": 75.7139},
    "Manipur":           {"lat": 24.6637, "lng": 93.9063},
    "Odisha":            {"lat": 20.9517, "lng": 85.0985},
    "Punjab":            {"lat": 31.1471, "lng": 75.3412},
    "Rajasthan":         {"lat": 27.0238, "lng": 74.2179},
    "Tamil Nadu":        {"lat": 11.1271, "lng": 78.6569},
    "Telangana":         {"lat": 18.1124, "lng": 79.0193},
    "Uttar Pradesh":     {"lat": 26.8467, "lng": 80.9462},
    "Uttarakhand":       {"lat": 30.0668, "lng": 79.0193},
    "West Bengal":       {"lat": 22.9868, "lng": 87.8550},
    "Jammu and Kashmir": {"lat": 33.7782, "lng": 76.5762},
}


def haversine_distance(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def load_mandi_coordinates() -> list:
    if not os.path.exists(COORDS_FILE):
        return []

    with open(COORDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_market_coordinates(market: str, district: str, state: str):
    data = load_mandi_coordinates()

    for row in data:
        if (
            row["market"].strip().lower() == market.strip().lower()
            and row["district"].strip().lower() == district.strip().lower()
            and row["state"].strip().lower() == state.strip().lower()
        ):
            return {
                "lat": row["lat"],
                "lng": row["lng"]
            }

    return None


def get_latest_prices(commodity: str, state: str, db: Session) -> list:
    subq = (
        db.query(
            MandiPrice.market,
            func.max(MandiPrice.arrival_date).label("latest_date")
        )
        .filter(
            func.lower(MandiPrice.commodity) == commodity.lower(),
            func.lower(MandiPrice.state) == state.lower()
        )
        .group_by(MandiPrice.market)
        .subquery()
    )

    results = (
        db.query(MandiPrice)
        .join(
            subq,
            (MandiPrice.market == subq.c.market) &
            (MandiPrice.arrival_date == subq.c.latest_date)
        )
        .filter(
            func.lower(MandiPrice.commodity) == commodity.lower(),
            func.lower(MandiPrice.state) == state.lower()
        )
        .order_by(desc(MandiPrice.arrival_date))
        .all()
    )

    return [_to_dict(r) for r in results]


def get_all_latest_prices(commodity: str, db: Session) -> list:
    subq = (
        db.query(
            MandiPrice.market,
            MandiPrice.state,
            func.max(MandiPrice.arrival_date).label("latest_date")
        )
        .filter(func.lower(MandiPrice.commodity) == commodity.lower())
        .group_by(MandiPrice.market, MandiPrice.state)
        .subquery()
    )

    results = (
        db.query(MandiPrice)
        .join(
            subq,
            (MandiPrice.market == subq.c.market) &
            (MandiPrice.state == subq.c.state) &
            (MandiPrice.arrival_date == subq.c.latest_date)
        )
        .filter(func.lower(MandiPrice.commodity) == commodity.lower())
        .order_by(desc(MandiPrice.arrival_date))
        .all()
    )

    return [_to_dict(r) for r in results]


def get_price_history(commodity: str, market: str, db: Session) -> list:
    results = (
        db.query(MandiPrice)
        .filter(
            func.lower(MandiPrice.commodity) == commodity.lower(),
            func.lower(MandiPrice.market) == market.lower()
        )
        .order_by(MandiPrice.arrival_date)
        .all()
    )
    return [_to_dict(r) for r in results]


def karnataka_rows_exist(commodity: str, db: Session) -> bool:
    row = (
        db.query(MandiPrice.id)
        .filter(
            func.lower(MandiPrice.state) == "karnataka",
            func.lower(MandiPrice.commodity) == commodity.lower()
        )
        .first()
    )
    return row is not None

# services/market_service.py — add this function

def find_nearest_from_json(farmer_lat: float, farmer_lng: float, top_n: int = 5) -> list:
    """Use mandi_coordinates.json directly — no DB needed."""
    data = load_mandi_coordinates()  # already exists in your code
    results = []

    for row in data:
        dist = haversine_distance(farmer_lat, farmer_lng, row["lat"], row["lng"])
        results.append({
            "market":   row["market"],
            "district": row.get("district", ""),
            "state":    row.get("state", ""),
            "lat":      row["lat"],
            "lng":      row["lng"],
            "distance_km": round(dist, 1),
        })

    results.sort(key=lambda x: x["distance_km"])
    return results[:top_n]


def find_best_mandi_for_commodity(
    farmer_lat: float, farmer_lng: float,
    commodity: str, radius_km: float, top_n: int, db
) -> list:
    """DB prices + mandi_coordinates.json coords — no state centroid fallback."""
    all_prices = get_all_latest_prices(commodity, db)
    results = []

    for record in all_prices:
        coords = get_market_coordinates(
            market=record["market"].strip(),
            district=record["district"].strip(),
            state=record["state"].strip(),
        )
        if not coords:
            continue  # skip if no exact coords — no centroid fallback

        dist = haversine_distance(farmer_lat, farmer_lng, coords["lat"], coords["lng"])
        if dist > radius_km:
            continue

        transport = round(dist * TRANSPORT_COST_PER_KM, 2)
        results.append({
            **record,
            "distance_km":    round(dist, 1),
            "transport_cost": transport,
            "net_price":      round(record["modal_price"] - transport, 2),
        })

    results.sort(key=lambda x: x["net_price"], reverse=True)
    return results[:top_n]

def find_nearby_mandis(
    farmer_lat: float,
    farmer_lng: float,
    commodity: str,
    radius_km: float,
    top_n: int,
    db: Session,
) -> list:
    all_prices = get_all_latest_prices(commodity, db)
    results = []

    for record in all_prices:
        state = record["state"].strip()
        district = record["district"].strip()
        market = record["market"].strip()

        # 1. First try exact market coordinates from JSON
        coords = get_market_coordinates(
            market=market,
            district=district,
            state=state
        )

        # 2. If exact market coords not found, fall back to state centroid
        if not coords:
            for state_name, state_coords in STATE_COORDS.items():
                if state.lower() == state_name.lower():
                    coords = state_coords
                    break

        if not coords:
            continue

        distance = haversine_distance(
            farmer_lat, farmer_lng, coords["lat"], coords["lng"]
        )

        if distance > radius_km:
            continue

        transport_cost = round(distance * TRANSPORT_COST_PER_KM, 2)
        net_price = round(record["modal_price"] - transport_cost, 2)

        results.append({
            **record,
            "distance_km": round(distance, 1),
            "transport_cost": transport_cost,
            "net_price": net_price,
            "market_lat": coords["lat"],
            "market_lng": coords["lng"],
        })

    results.sort(key=lambda x: x["net_price"], reverse=True)
    return results[:top_n]


def _to_dict(r: MandiPrice) -> dict:
    return {
        "state": r.state,
        "district": r.district,
        "market": r.market,
        "commodity": r.commodity,
        "variety": r.variety,
        "min_price": float(r.min_price) if r.min_price is not None else 0,
        "max_price": float(r.max_price) if r.max_price is not None else 0,
        "modal_price": float(r.modal_price) if r.modal_price is not None else 0,
        "date": str(r.arrival_date),
    }