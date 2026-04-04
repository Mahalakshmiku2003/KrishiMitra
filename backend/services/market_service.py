import math
from sqlalchemy import select

from backend.db.models import MandiPrice  # adjust if your model name differs


async def get_price_history(commodity: str, db):
    try:
        result = await db.execute(
            select(MandiPrice).where(MandiPrice.commodity.ilike(f"%{commodity}%"))
        )
        rows = result.scalars().all()

        # return simple list of prices (for prediction)
        return [r.modal_price for r in rows if r.modal_price]

    except Exception as e:
        print("❌ DB error in get_price_history:", e)
        return []


# -----------------------------
# Utility: Distance (Haversine)
# -----------------------------
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # km

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# -----------------------------
# Fetch all latest prices
# -----------------------------
async def get_all_latest_prices(commodity: str, db):
    try:
        result = await db.execute(
            select(MandiPrice).where(MandiPrice.commodity.ilike(f"%{commodity}%"))
        )
        rows = result.scalars().all()
        return rows
    except Exception as e:
        print("❌ DB error in get_all_latest_prices:", e)
        return []


# -----------------------------
# Find best mandi
# -----------------------------
def _dedupe_latest_rows(rows):
    best = {}
    for row in rows:
        mk = getattr(row, "market", "") or ""
        dstr = getattr(row, "district", "") or ""
        key = (mk, dstr)
        prev = best.get(key)
        ad = getattr(row, "arrival_date", None)
        if prev is None:
            best[key] = row
            continue
        prev_ad = getattr(prev, "arrival_date", None)
        if ad is not None and (prev_ad is None or ad > prev_ad):
            best[key] = row
    return list(best.values())


async def find_best_mandi_for_commodity(
    farmer_lat: float | None = None,
    farmer_lng: float | None = None,
    commodity: str = "",
    radius_km: int = 300,
    top_n: int = 3,
    db=None,
    location_name: str | None = None,
):
    if not commodity:
        return []

    all_prices = await get_all_latest_prices(commodity, db)

    if location_name:
        ln = (location_name or "").strip().lower()
        if ln:
            matched = []
            for row in all_prices:
                dist = (getattr(row, "district", None) or "").lower()
                mkt = (getattr(row, "market", None) or "").lower()
                if (
                    ln in dist
                    or dist in ln
                    or ln in mkt
                    or mkt in ln
                ):
                    matched.append(row)
            if matched:
                rows = _dedupe_latest_rows(matched)
                rows.sort(
                    key=lambda r: float(getattr(r, "modal_price", 0) or 0),
                    reverse=True,
                )
                out = []
                for r in rows[:top_n]:
                    out.append(
                        {
                            "market": getattr(r, "market", "Unknown"),
                            "modal_price": float(getattr(r, "modal_price", 0) or 0),
                            "district": getattr(r, "district", "") or "",
                            "distance": "?",
                            "distance_km": None,
                        }
                    )
                return out

    if farmer_lat is None or farmer_lng is None:
        return []

    mandis = []

    for row in all_prices:
        try:
            mandi_lat = getattr(row, "lat", None)
            mandi_lng = getattr(row, "lng", None)

            if mandi_lat is None or mandi_lng is None:
                continue

            distance = calculate_distance(farmer_lat, farmer_lng, mandi_lat, mandi_lng)

            if distance > radius_km:
                continue

            modal_price = getattr(row, "modal_price", 0)

            # simple score: price advantage - distance penalty
            score = modal_price - (distance * 2)

            mandis.append(
                {
                    "market": getattr(row, "market", "Unknown"),
                    "modal_price": modal_price,
                    "distance": round(distance, 2),
                    "score": score,
                }
            )

        except Exception as e:
            print("⚠️ Error processing mandi row:", e)
            continue

    # sort by score
    mandis.sort(key=lambda x: x["score"], reverse=True)

    return mandis[:top_n]
