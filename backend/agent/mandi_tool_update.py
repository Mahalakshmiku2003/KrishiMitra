import os
import math
import json
import asyncio
from functools import partial
from groq import AsyncGroq

KARNATAKA = "karnataka"
PAGE_SIZE = 3

# { farmer_id: { "remaining": [...], "commodity": str|None, "offer_gps": bool, "language": str } }
_mandi_pages: dict[str, dict] = {}


async def handle_more(farmer_id: str) -> str | None:
    page = _mandi_pages.get(farmer_id)
    if not page or not page.get("remaining"):
        _mandi_pages.pop(farmer_id, None)
        return None

    remaining = page["remaining"]
    commodity = page.get("commodity")
    offer_gps = page.get("offer_gps", False)
    language = page.get("language", "Hindi")

    batch = remaining[:PAGE_SIZE]
    leftover = remaining[PAGE_SIZE:]

    if leftover:
        _mandi_pages[farmer_id] = {
            "remaining": leftover,
            "commodity": commodity,
            "offer_gps": offer_gps,
            "language": language,
        }
    else:
        _mandi_pages.pop(farmer_id, None)

    has_more = bool(leftover)
    return await _format_batch(
        mandis=batch,
        commodity=commodity,
        offer_gps=offer_gps,
        has_more=has_more,
        language=language,
        is_continuation=True,
    )


def has_pending_page(farmer_id: str) -> bool:
    return farmer_id in _mandi_pages and bool(_mandi_pages[farmer_id].get("remaining"))


def _coord_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "mandi_coordinates.json",
    )


def _load_coordinates() -> list[dict]:
    try:
        with open(_coord_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[MandiTool] Could not load mandi_coordinates.json: {e}")
        return []


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _gps_offer(language: str) -> str:
    lang = (language or "Hindi").strip().lower()
    if lang == "english":
        return (
            "\n\n📍 For even more accurate results, share your location:"
            "\nAttachment -> Location -> Send Current Location"
        )
    if lang == "kannada":
        return (
            "\n\n📍 ಇನ್ನೂ ಸರಿಯಾದ ಫಲಿತಾಂಶಕ್ಕೆ ನಿಮ್ಮ ಲೊಕೇಶನ್ ಹಂಚಿಕೊಳ್ಳಿ:"
            "\nAttachment -> Location -> Send Current Location"
        )
    return (
        "\n\n📍 Aur sahi result ke liye apni location share karein:"
        "\nAttachment -> Location -> Send Current Location"
    )


async def _format_batch(
    mandis: list[dict],
    commodity: str | None,
    offer_gps: bool,
    has_more: bool,
    language: str = "Hindi",
    is_continuation: bool = False,
) -> str:
    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

    continuation_note = (
        "This is a continuation of a previous list. Do not greet again."
        if is_continuation
        else ""
    )

    if has_more:
        if (language or "Hindi").strip().lower() == "english":
            more_note = "After the list, add exactly this line: 'Reply MORE to see the remaining mandis 👇'"
        elif (language or "Hindi").strip().lower() == "kannada":
            more_note = "After the list, add exactly this line: 'ಉಳಿದ ಮಂಡಿಗಳನ್ನು ನೋಡಲು MORE ಎಂದು reply ಮಾಡಿ 👇'"
        else:
            more_note = "After the list, add exactly this line: '*MORE* reply karein baaki mandis dekhne ke liye 👇'"
    else:
        if (language or "Hindi").strip().lower() == "english":
            more_note = "End with: 'Need any other help? 🌾'"
        elif (language or "Hindi").strip().lower() == "kannada":
            more_note = "End with: 'ಇನ್ನೇನಾದರೂ ಸಹಾಯ ಬೇಕೇ? 🌾'"
        else:
            more_note = "End with: 'Koi aur madad chahiye? 🌾'"

    data_str = json.dumps(mandis, ensure_ascii=False, indent=2)

    prompt = f"""You are KrishiMitra, a farming assistant for Indian farmers.

Format this Karnataka mandi data into a clean WhatsApp reply.
Commodity filter: {commodity or "all commodities"}
Reply language: {language}
{continuation_note}

Data:
{data_str}

Rules:
- Reply fully in {language}
- Keep the tone short, practical, and farmer-friendly
- Show ALL mandis in the provided data
- For each mandi, show:
  - mandi name
  - district
  - modal price in Rs/quintal if available
  - distance_km if available
  - net_price_est if available
- Ranking rule:
  - If net_price_est is available, the best mandi is the one with the HIGHEST net_price_est
  - Otherwise, if modal_price is available, the best mandi is the one with the HIGHEST modal_price
  - If price is missing, do NOT call any mandi best
- Never say "sabse sasta" unless explicitly referring to the lowest price
- Only bold the best mandi when the data clearly supports it
- Do not contradict the numbers in the data
- {more_note}"""

    resp = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.2,
    )
    reply = (resp.choices[0].message.content or "").strip()
    return reply + (_gps_offer(language) if offer_gps else "")


async def _format_no_data(
    commodity: str | None,
    context: str,
    offer_gps: bool,
    language: str = "Hindi",
) -> str:
    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    prompt = (
        f"Farmer asked about mandi prices{f' for {commodity}' if commodity else ''}. "
        f"{context} "
        f"No Karnataka mandi data found. "
        f"Reply in {language}. "
        f"Suggest checking Agmarknet.gov.in, local mandi, or trying again. "
        f"Keep it short and farmer-friendly."
    )
    resp = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.3,
    )
    reply = (resp.choices[0].message.content or "").strip()
    return reply + (_gps_offer(language) if offer_gps else "")


async def _paginate_and_reply(
    farmer_id: str | None,
    mandis: list[dict],
    commodity: str | None,
    context: str,
    offer_gps: bool,
    language: str = "Hindi",
) -> str:
    if not mandis:
        return await _format_no_data(commodity, context, offer_gps, language)

    first_batch = mandis[:PAGE_SIZE]
    remaining = mandis[PAGE_SIZE:]
    has_more = bool(remaining)

    if has_more and farmer_id:
        _mandi_pages[farmer_id] = {
            "remaining": remaining,
            "commodity": commodity,
            "offer_gps": offer_gps,
            "language": language,
        }
    elif farmer_id:
        _mandi_pages.pop(farmer_id, None)

    return await _format_batch(
        mandis=first_batch,
        commodity=commodity,
        offer_gps=offer_gps,
        has_more=has_more,
        language=language,
    )


def _sync_enrich_from_db(market_name: str, commodity: str | None):
    from backend.services.db import SessionLocal
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


async def _async_enrich_from_db(market_name: str, commodity: str | None):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        partial(_sync_enrich_from_db, market_name, commodity),
    )


def _sync_fetch_city_rows(city: str, commodity: str | None):
    from backend.services.db import SessionLocal
    from sqlalchemy import text

    base_where = """
        WHERE (
            LOWER(district) LIKE :city
            OR LOWER(market) LIKE :city
        )
        AND LOWER(state) = :state
    """
    params = {"city": f"%{city.lower()}%", "state": KARNATAKA}

    if commodity:
        query = text(
            f"""
            SELECT market, district, state, commodity,
                   min_price, max_price, modal_price, arrival_date
            FROM mandi_prices
            {base_where}
            AND LOWER(commodity) = :commodity
            ORDER BY modal_price DESC
            """
        )
        params["commodity"] = commodity.lower()
    else:
        query = text(
            f"""
            SELECT DISTINCT ON (market)
                   market, district, state, commodity,
                   min_price, max_price, modal_price, arrival_date
            FROM mandi_prices
            {base_where}
            ORDER BY market, arrival_date DESC
            """
        )

    with SessionLocal() as db:
        return db.execute(query, params).fetchall()


async def _async_fetch_city_rows(city: str, commodity: str | None):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        partial(_sync_fetch_city_rows, city, commodity),
    )


async def get_mandis_for_gps(
    lat: float,
    lng: float,
    commodity: str | None = None,
    farmer_id: str | None = None,
    language: str = "Hindi",
) -> str:
    all_coords = _load_coordinates()

    ka_geo = [
        m
        for m in all_coords
        if m.get("lat") and m.get("lng") and m.get("state", "").lower() == KARNATAKA
    ]

    if not ka_geo:
        return await _format_no_data(
            commodity,
            "No geocoded Karnataka mandi data.",
            offer_gps=False,
            language=language,
        )

    for m in ka_geo:
        m["_dist"] = round(_haversine_km(lat, lng, m["lat"], m["lng"]), 1)

    nearby = sorted(ka_geo, key=lambda x: x["_dist"])

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
        farmer_id=farmer_id,
        mandis=mandis,
        commodity=commodity,
        context=context,
        offer_gps=False,
        language=language,
    )


async def get_mandis_for_city(
    city: str,
    commodity: str | None = None,
    farmer_id: str | None = None,
    language: str = "Hindi",
) -> str:
    mandis = []
    from_json = False

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

    if not mandis:
        all_coords = _load_coordinates()
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
        farmer_id=farmer_id,
        mandis=mandis,
        commodity=commodity,
        context=context,
        offer_gps=True,
        language=language,
    )
