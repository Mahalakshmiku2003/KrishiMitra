"""
agent/mandi_tool_update.py
Karnataka-optimized mandi lookup.

Flow:
  GPS saved  → nearest mandis by distance (coordinates.json) + DB prices
  City named → DB by district/state=Karnataka + JSON fallback + GPS offer
  No context → caller returns __LOCATION_REQUESTED__

Pagination:
  <= 3 mandis → show all, no MORE prompt
  >  3 mandis → show first 3, store rest, prompt "Reply MORE"
  User replies MORE → next 3 shown, repeat until exhausted
  Works for any number of markets (6, 20, 50+)

Fixes applied:
  - [BUG] Sync SessionLocal used inside async functions → now runs in
    asyncio thread executor so the event loop is never blocked.
  - [BUG] Operator-precedence bug in JSON fallback filter (missing parens
    around the OR clause) → state check was never applied to the second
    condition, letting non-Karnataka entries leak through.
"""

import os
import math
import json
import asyncio
from functools import partial
from groq import AsyncGroq

KARNATAKA = "karnataka"
PAGE_SIZE = 3  # mandis shown per message

# ── In-memory pagination store ────────────────────────────────────────────────
# { farmer_id: { "remaining": [...], "commodity": str|None, "offer_gps": bool } }
_mandi_pages: dict[str, dict] = {}


# ── Public: handle "MORE" reply ───────────────────────────────────────────────


async def handle_more(farmer_id: str) -> str | None:
    """
    Called when farmer replies 'more' / 'aur' / 'aur dikhao'.
    Returns next page reply, or None if no pending pages.
    """
    page = _mandi_pages.get(farmer_id)
    if not page or not page.get("remaining"):
        _mandi_pages.pop(farmer_id, None)
        return None

    remaining = page["remaining"]
    commodity = page.get("commodity")
    offer_gps = page.get("offer_gps", False)

    batch = remaining[:PAGE_SIZE]
    leftover = remaining[PAGE_SIZE:]

    if leftover:
        _mandi_pages[farmer_id] = {
            "remaining": leftover,
            "commodity": commodity,
            "offer_gps": offer_gps,
        }
    else:
        _mandi_pages.pop(farmer_id, None)

    has_more = bool(leftover)
    return await _format_batch(
        batch, commodity, offer_gps, has_more, is_continuation=True
    )


def has_pending_page(farmer_id: str) -> bool:
    """Check if farmer has more mandi results waiting."""
    return farmer_id in _mandi_pages and bool(_mandi_pages[farmer_id].get("remaining"))


# ── Coordinates JSON path ─────────────────────────────────────────────────────


def _coord_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "mandi_coordinates.json"
    )


def _load_coordinates() -> list[dict]:
    try:
        with open(_coord_path()) as f:
            return json.load(f)
    except Exception as e:
        print(f"[MandiTool] Could not load mandi_coordinates.json: {e}")
        return []


# ── Haversine distance ────────────────────────────────────────────────────────


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── GPS offer footer ──────────────────────────────────────────────────────────

GPS_OFFER = (
    "\n\n📍 *Aur sahi result ke liye apni location share karein:*"
    "\nAttachment → Location → Send Current Location"
)


# ── Core formatter: one batch of mandis ──────────────────────────────────────


async def _format_batch(
    mandis: list[dict],
    commodity: str | None,
    offer_gps: bool,
    has_more: bool,
    is_continuation: bool = False,
) -> str:
    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

    continuation_note = (
        "This is a continuation of a previous list — do NOT greet again, jump straight to the list."
        if is_continuation
        else ""
    )
    more_note = (
        "After the list, add exactly this line on its own: '*MORE* reply karein baaki mandis dekhne ke liye 👇'"
        if has_more
        else "End with: 'Koi aur madad chahiye? 🌾'"
    )

    data_str = json.dumps(mandis, ensure_ascii=False, indent=2)
    prompt = f"""You are KrishiMitra, a farming assistant for Indian farmers.

Format this Karnataka mandi data into a clean WhatsApp reply.
Commodity filter: {commodity or "all commodities"}
{continuation_note}

Data:
{data_str}

Rules:
- Reply in Hindi
- Show ALL mandis in the data provided (do not skip any)
- Each entry: mandi name, district, modal price Rs/quintal (skip price if null)
- *Bold* the best priced mandi
- If distance_km and net_price_est available, show them
- SHORT and practical
- {more_note}"""

    resp = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.2,
    )
    reply = resp.choices[0].message.content
    return reply + (GPS_OFFER if offer_gps else "")


async def _format_no_data(commodity: str | None, context: str, offer_gps: bool) -> str:
    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    prompt = (
        f"Farmer asked about mandi prices{f' for {commodity}' if commodity else ''}. "
        f"{context} "
        f"No Karnataka mandi data found. "
        f"In Hindi, suggest: check Agmarknet.gov.in, call local mandi, or try again. "
        f"End with: 'Koi aur madad chahiye? 🌾'"
    )
    resp = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.3,
    )
    reply = resp.choices[0].message.content
    return reply + (GPS_OFFER if offer_gps else "")


# ── Paginate + send first batch ───────────────────────────────────────────────


async def _paginate_and_reply(
    farmer_id: str | None,
    mandis: list[dict],
    commodity: str | None,
    context: str,
    offer_gps: bool,
) -> str:
    if not mandis:
        return await _format_no_data(commodity, context, offer_gps)

    first_batch = mandis[:PAGE_SIZE]
    remaining = mandis[PAGE_SIZE:]
    has_more = bool(remaining)

    # Store remaining pages only if we have a farmer_id to key on
    if has_more and farmer_id:
        _mandi_pages[farmer_id] = {
            "remaining": remaining,
            "commodity": commodity,
            "offer_gps": offer_gps,
        }
    elif farmer_id:
        # Clear any stale pages for this farmer
        _mandi_pages.pop(farmer_id, None)

    return await _format_batch(first_batch, commodity, offer_gps, has_more)


# ── DB helpers: run sync SQLAlchemy in a thread so the event loop isn't blocked


def _sync_enrich_from_db(market_name: str, commodity: str | None) -> dict | None:
    """
    Runs synchronously — always call via _async_enrich_from_db().
    Opens its own short-lived session and closes it immediately.
    """
    from services.db import SessionLocal
    from sqlalchemy import text

    query = """
        SELECT modal_price, min_price, max_price, arrival_date, commodity
        FROM mandi_prices
        WHERE LOWER(market) = :market
          AND LOWER(state) = :state
    """
    params = {"market": market_name.lower(), "state": KARNATAKA}
    if commodity:
        query += " AND LOWER(commodity) = :commodity"
        params["commodity"] = commodity.lower()
    query += " ORDER BY arrival_date DESC LIMIT 1"

    with SessionLocal() as db:
        return db.execute(text(query), params).fetchone()


async def _async_enrich_from_db(market_name: str, commodity: str | None) -> dict | None:
    """Offload sync DB call to a thread executor — keeps event loop free."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, partial(_sync_enrich_from_db, market_name, commodity)
    )


def _sync_fetch_city_rows(city: str, commodity: str | None) -> list:
    """
    Full city/district DB lookup — sync, run via executor.
    Returns raw row tuples.
    """
    from services.db import SessionLocal
    from sqlalchemy import text

    base_where = """
        WHERE (
            LOWER(district) LIKE :city
            OR LOWER(market)  LIKE :city
        )
        AND LOWER(state) = :state
    """
    params = {"city": f"%{city.lower()}%", "state": KARNATAKA}

    if commodity:
        query = text(f"""
            SELECT market, district, state, commodity,
                   min_price, max_price, modal_price, arrival_date
            FROM mandi_prices
            {base_where}
            AND LOWER(commodity) = :commodity
            ORDER BY modal_price DESC
        """)
        params["commodity"] = commodity.lower()
    else:
        query = text(f"""
            SELECT DISTINCT ON (market)
                   market, district, state, commodity,
                   min_price, max_price, modal_price, arrival_date
            FROM mandi_prices
            {base_where}
            ORDER BY market, arrival_date DESC
        """)

    with SessionLocal() as db:
        return db.execute(query, params).fetchall()


async def _async_fetch_city_rows(city: str, commodity: str | None) -> list:
    """Offload sync city DB lookup to executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, partial(_sync_fetch_city_rows, city, commodity)
    )


# ── FLOW 1: GPS-based (distance + price) ─────────────────────────────────────


async def get_mandis_for_gps(
    lat: float,
    lng: float,
    commodity: str | None = None,
    farmer_id: str = None,
) -> str:
    all_coords = _load_coordinates()

    # Only Karnataka entries with valid lat/lng
    ka_geo = [
        m
        for m in all_coords
        if m.get("lat") and m.get("lng") and m.get("state", "").lower() == KARNATAKA
    ]

    if not ka_geo:
        print("[MandiTool] No geocoded Karnataka entries in coordinates JSON")
        return await _format_no_data(
            commodity, "No geocoded Karnataka mandi data.", offer_gps=False
        )

    # Sort by distance — no artificial cap, pagination handles display
    for m in ka_geo:
        m["_dist"] = round(_haversine_km(lat, lng, m["lat"], m["lng"]), 1)
    nearby = sorted(ka_geo, key=lambda x: x["_dist"])

    # Enrich each market with DB price — offloaded to thread executor
    mandis = []
    try:
        for m in nearby:
            market_name = m.get("market", "Unknown")
            row = await _async_enrich_from_db(market_name, commodity)
            entry = {
                "market": market_name,
                "district": m.get("district", ""),
                "state": "Karnataka",
                "distance_km": m["_dist"],
            }
            if row:
                transport_cost = round(m["_dist"] * 2.5, 2)
                entry.update(
                    {
                        "commodity": row[4] if not commodity else commodity,
                        "modal_price": row[0],
                        "min_price": row[1],
                        "max_price": row[2],
                        "arrival_date": str(row[3]) if row[3] else None,
                        "transport_cost_est": transport_cost,
                        "net_price_est": round(row[0] - transport_cost, 2),
                    }
                )
            mandis.append(entry)
    except Exception as e:
        print(f"[MandiTool] GPS DB enrichment error: {e}")
        mandis = [
            {
                "market": m.get("market", "Unknown"),
                "district": m.get("district", ""),
                "state": "Karnataka",
                "distance_km": m["_dist"],
            }
            for m in nearby
        ]

    context = (
        f"Farmer GPS: {lat:.4f},{lng:.4f}. Karnataka mandis sorted by distance. "
        + (f"Commodity: {commodity}." if commodity else "")
    )
    return await _paginate_and_reply(
        farmer_id, mandis, commodity, context, offer_gps=False
    )


# ── FLOW 2: City/district-based ───────────────────────────────────────────────


async def get_mandis_for_city(
    city: str,
    commodity: str | None = None,
    farmer_id: str = None,
) -> str:
    """
    Step 1: DB WHERE (district OR market LIKE city) AND state = Karnataka
    Step 2: If empty → filter coordinates JSON by district
    Step 3: Paginate — first 3 shown, rest stored for MORE replies
    """
    mandis = []
    from_json = False

    # ── Step 1: DB lookup via executor (no event-loop blocking) ───────────────
    try:
        rows = await _async_fetch_city_rows(city, commodity)
        mandis = [
            {
                "market": r[0],
                "district": r[1],
                "state": r[2],
                "commodity": r[3],
                "min_price": r[4],
                "max_price": r[5],
                "modal_price": r[6],
                "arrival_date": str(r[7]) if r[7] else None,
            }
            for r in rows
        ]
        print(f"[MandiTool] DB: {len(mandis)} rows for city='{city}' state=Karnataka")
    except Exception as e:
        print(f"[MandiTool] DB error for city '{city}': {e}")

    # ── Step 2: JSON fallback if DB empty ─────────────────────────────────────
    if not mandis:
        print(f"[MandiTool] Falling back to coordinates JSON for '{city}'")
        all_coords = _load_coordinates()

        # FIX: added parens around the OR so the state check applies to BOTH
        # conditions. Without parens, Python's operator precedence meant the
        # state filter only applied to the market-name branch, letting
        # non-Karnataka entries pass through the district branch.
        matched = [
            m
            for m in all_coords
            if (
                city.lower() in m.get("district", "").lower()
                or city.lower() in m.get("market", "").lower()
            )
            and m.get("state", "").lower() == KARNATAKA
        ]

        if matched:
            mandis = [
                {
                    "market": m.get("market", "Unknown"),
                    "district": m.get("district", ""),
                    "state": "Karnataka",
                    "modal_price": None,
                }
                for m in matched
            ]
            from_json = True
            print(f"[MandiTool] JSON fallback: {len(mandis)} entries for '{city}'")

    context = (
        f"Farmer asked about mandis in {city}, Karnataka. "
        + ("Live price data available. " if not from_json and mandis else "")
        + ("No live prices — showing mandi names only. " if from_json else "")
    )
    return await _paginate_and_reply(
        farmer_id, mandis, commodity, context, offer_gps=True
    )
