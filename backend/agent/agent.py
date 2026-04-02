# backend/agent/agent.py
import os
from groq import AsyncGroq
from dotenv import load_dotenv
from agent.tools import (
    get_weather,
    get_mandi_price,
    get_treatment,
    get_govt_schemes,
    get_disease_progression,
)
from services.location_state import _pending_location

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
from backend.farmer_store import get_farmer_location

client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

memory_store = {}

# Keywords that trigger MORE pagination
MORE_KEYWORDS = {"more", "aur", "aur dikhao", "next", "aage", "aur batao"}


def get_history(farmer_id: str) -> list:
    if farmer_id not in memory_store:
        memory_store[farmer_id] = []
    return memory_store[farmer_id]


def save_message(farmer_id: str, role: str, content: str):
    history = get_history(farmer_id)
    history.append({"role": role, "content": content})
    if len(history) > 10:
        memory_store[farmer_id] = history[-10:]


def build_system_prompt(language: str) -> str:
    lang_instruction = {
        "Hindi": "ALWAYS reply in Hindi (Devanagari script). Never switch to English.",
        "Kannada": "ALWAYS reply in Kannada (Kannada script). Never switch to English.",
        "English": "ALWAYS reply in English.",
    }.get(language, "Reply in the same language as the farmer.")

    return f"""You are KrishiMitra, a friendly AI farming assistant for Indian farmers.

LANGUAGE RULE: {lang_instruction}

IMPORTANT: Never mention tool names like get_treatment or get_nearby_mandis
in your reply. Just use the data they return naturally in your response.

When farmer sends crop photo with diagnosis:
1. Tell disease name and severity clearly
2. Give specific treatment with medicine names and dosage
3. Warn how fast it spreads if untreated
4. Give urgency level

When farmer asks about prices:
1. Give current rates
2. Suggest nearest mandi to sell

When farmer asks about schemes:
1. List schemes with how to apply

Rules:
- Keep replies SHORT and PRACTICAL
- Never mention tool names in reply
- Format the replies in clean way
- Always end with: 'Koi aur madad chahiye? 🌾'
"""


async def process_message(
    farmer_id: str,
    message: str,
    disease_result: dict = None,
    language: str = "Hindi",
) -> str:
    try:
        # ── Handle MORE pagination first ──────────────────────────────────────
        msg_stripped = message.strip().lower()
        if msg_stripped in MORE_KEYWORDS:
            from agent.mandi_tool_update import handle_more, has_pending_page

            if has_pending_page(farmer_id):
                reply = await handle_more(farmer_id)
                if reply:
                    return reply

        if disease_result and not disease_result.get("error"):
            disease = disease_result.get("disease", "")
            conf = disease_result.get("confidence", "")
            severity = disease_result.get("severity", {})
            urgency = disease_result.get("urgency", "")
            prog = disease_result.get("progression", {})

            context = (
                f"CROP PHOTO ANALYSIS RESULT:\n"
                f"Disease   : {disease}\n"
                f"Confidence: {conf}\n"
                f"Severity  : {severity.get('level', 'Unknown')} — "
                f"{severity.get('description', '')}\n"
                f"Urgency   : {urgency}\n"
            )
            if prog:
                context += (
                    f"If untreated: {prog.get('day_7_spread', '?')} "
                    f"crop affected in 7 days\n"
                    f"Warning: {prog.get('warning', '')}\n"
                )
            message = f"{context}\nFarmer message: {message or 'Please help me'}"

        history = get_history(farmer_id)
        system_prompt = build_system_prompt(language)
        messages = (
            [{"role": "system", "content": system_prompt}]
            + history
            + [{"role": "user", "content": message}]
        )

        tool_result = await use_tools(message, disease_result, farmer_id)

        if tool_result == "__LOCATION_REQUESTED__":
            msg_lower = message.lower()
            explicit_crop = None
            for c in [
                "tomato",
                "potato",
                "onion",
                "wheat",
                "rice",
                "cotton",
                "corn",
                "grape",
                "pepper",
                "mango",
                "banana",
                "garlic",
                "ginger",
                "brinjal",
                "cabbage",
                "cauliflower",
                "carrot",
                "chilli",
                "groundnut",
                "soybean",
            ]:
                if c in msg_lower:
                    explicit_crop = c
                    break
            crop_str = f"*{explicit_crop}*" if explicit_crop else "mandis"
            return (
                f"Aapki location save karni hai taaki {crop_str} ke liye "
                f"seedha jawab de sakoon!\n\n"
                f"Please apni *WhatsApp location share karein* 📍\n"
                f"(Attachment → Location → Send Current Location)\n\n"
                f"Koi aur madad chahiye? 🌾"
            )

        if tool_result and tool_result.startswith("__DIRECT_REPLY__"):
            return tool_result.replace("__DIRECT_REPLY__", "", 1)

        if tool_result:
            messages.append(
                {"role": "user", "content": f"Additional data:\n{tool_result}"}
            )

        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=600,
        )

        reply = response.choices[0].message.content
        save_message(farmer_id, "user", message)
        save_message(farmer_id, "assistant", reply)
        return reply

    except Exception as e:
        print(f"❌ process_message error: {e}")
        return f"Sorry, please try again. Error: {str(e)}"


async def use_tools(
    message: str, disease_result: dict = None, farmer_id: str = None
) -> str:
    msg_lower = message.lower()
    results = []

    CROP_LIST = [
        "tomato",
        "potato",
        "onion",
        "wheat",
        "rice",
        "cotton",
        "corn",
        "grape",
        "pepper",
        "mango",
        "banana",
        "garlic",
        "ginger",
        "brinjal",
        "cabbage",
        "cauliflower",
        "carrot",
        "chilli",
        "groundnut",
        "soybean",
    ]

    CITY_LIST = [
        "salem",
        "pune",
        "mumbai",
        "delhi",
        "bangalore",
        "bengaluru",
        "hyderabad",
        "nashik",
        "nagpur",
        "chennai",
        "kolkata",
        "ahmedabad",
        "jaipur",
        "lucknow",
        "patna",
        "bhopal",
        "indore",
        "chandigarh",
        "ludhiana",
        "kochi",
        "coimbatore",
        "madurai",
        "warangal",
        "rajkot",
        "surat",
        "amritsar",
        "agra",
        "varanasi",
        # Karnataka districts
        "hubli",
        "dharwad",
        "belagavi",
        "belgaum",
        "mysuru",
        "mysore",
        "tumkur",
        "davangere",
        "shivamogga",
        "shimoga",
        "ballari",
        "bellary",
        "kalaburagi",
        "gulbarga",
        "mangaluru",
        "mangalore",
        "udupi",
        "vijayapura",
        "bijapur",
        "bidar",
        "raichur",
        "koppal",
        "gadag",
        "haveri",
        "chitradurga",
        "chikkamagaluru",
        "hassan",
        "mandya",
        "ramanagara",
        "kolar",
        "bagalkot",
        "yadgir",
        "chamarajanagar",
        "kodagu",
        "chikkaballapur",
        "hospet",
        "hosapete",
    ]

    explicit_crop = None
    for c in CROP_LIST:
        if c in msg_lower:
            explicit_crop = c
            break

    explicit_city = None
    for city in CITY_LIST:
        if city in msg_lower:
            explicit_city = city
            break

    # ── Disease tools ─────────────────────────────────────────────────────────
    if disease_result and not disease_result.get("error"):
        disease = disease_result.get("disease", "")
        if disease and disease != "Could not analyze":
            results.append(get_treatment.run(disease))
            results.append(get_disease_progression.run(disease))

    # ── Weather ───────────────────────────────────────────────────────────────
    if any(
        w in msg_lower
        for w in ["weather", "rain", "spray", "mausam", "barish", "humid"]
    ):
        location = explicit_city or extract_location(message)
        results.append(get_weather.run(location))

    # ── NEW: Price alert subscription ─────────────────────────────────────────
    # Only fires if message has BOTH a crop AND alert-intent words AND a number
    # Does NOT interfere with "tomato price?" or "mandi" queries
    alert_match = _parse_price_alert(msg_lower)
    if alert_match:
        from farmer_store import save_price_alert

        save_price_alert(
            phone=farmer_id,
            commodity=alert_match["commodity"],
            target_price=alert_match["price"],
            direction=alert_match["direction"],
        )
        return (
            f"__DIRECT_REPLY__✅ Alert set!\n\n"
            f"Jab *{alert_match['commodity'].title()}* ka bhav "
            f"Rs.*{alert_match['price']}*/quintal se "
            f"{'upar' if alert_match['direction'] == 'above' else 'neeche'} "
            f"jayega, main aapko turant bata dunga! 🔔\n\n"
            f"Koi aur madad chahiye? 🌾"
        )

    # ── NEW: Price prediction ─────────────────────────────────────────────────
    # Only fires on explicit prediction words — won't trigger on "tomato price?"
    if any(
        w in msg_lower
        for w in [
            "predict",
            "forecast",
            "rise",
            "fall",
            "badhega",
            "ghategaa",
            "trend",
            "future",
        ]
    ):
        crop = _extract_crop_explicit(msg_lower)
        if crop:
            return await _get_price_prediction(crop, farmer_id)

    # Price tool — keep this separate from nearby
    if any(w in msg_lower for w in ["price", "rate", "bhav"]):
        crop = extract_crop(message)
        results.append(get_mandi_price.run(crop))
    # ── Mandi / market / sell / price / rate ──────────────────────────────────
    mandi_keywords = [
        "nearby",
        "nearest",
        "closest",
        "paas",
        "kahan",
        "mandi",
        "sell",
        "market",
        "markets",
        "where to sell",
        "kahan bechu",
        "price",
        "rate",
        "bhav",
    ]
    if any(w in msg_lower for w in mandi_keywords):
        from agent.mandi_tool_update import get_mandis_for_gps, get_mandis_for_city

        saved = get_farmer_location(farmer_id) if farmer_id else None

        if explicit_city:
            mandi_reply = await get_mandis_for_city(
                city=explicit_city,
                commodity=explicit_crop,
                farmer_id=farmer_id,
            )
            return f"__DIRECT_REPLY__{mandi_reply}"

        elif saved:
            mandi_reply = await get_mandis_for_gps(
                lat=saved["lat"],
                lng=saved["lng"],
                commodity=explicit_crop,
                farmer_id=farmer_id,
            )
            return f"__DIRECT_REPLY__{mandi_reply}"

        else:
            _pending_location[farmer_id] = {
                "waiting": "mandi",
                "commodity": explicit_crop,
            }
            return "__LOCATION_REQUESTED__"

    # ── Govt schemes ──────────────────────────────────────────────────────────
    if any(
        w in msg_lower
        for w in ["scheme", "subsidy", "insurance", "yojana", "sarkar", "sarkari"]
    ):
        results.append(get_govt_schemes.run("India"))

    return "\n\n".join(results) if results else ""


def extract_location(message: str) -> str:
    cities = [
        "pune",
        "mumbai",
        "delhi",
        "bangalore",
        "bengaluru",
        "hyderabad",
        "nashik",
        "nagpur",
        "chennai",
        "kolkata",
        "ahmedabad",
        "jaipur",
        "lucknow",
        "patna",
        "bhopal",
        "indore",
        "chandigarh",
        "ludhiana",
        "amritsar",
        "kochi",
    ]
    msg_lower = message.lower()
    for city in cities:
        if city in msg_lower:
            return city.capitalize()
    return "Pune"


def extract_crop(message: str) -> str:
    crops = [
        "tomato",
        "potato",
        "onion",
        "wheat",
        "rice",
        "cotton",
        "corn",
        "grape",
        "pepper",
        "mango",
        "banana",
    ]
    msg_lower = message.lower()
    for crop in crops:
        if crop in msg_lower:
            return crop
    return "tomato"


import re


def _extract_crop_explicit(msg_lower: str) -> str | None:
    """Returns crop only if explicitly mentioned. Never defaults."""
    for c in [
        "tomato",
        "potato",
        "onion",
        "wheat",
        "rice",
        "cotton",
        "corn",
        "grape",
        "pepper",
        "mango",
        "banana",
    ]:
        if c in msg_lower:
            return c
    return None


def _parse_price_alert(msg_lower: str) -> dict | None:
    """
    Returns alert dict only if ALL three are present:
    1. a crop name
    2. an alert-intent word (alert/notify/bata/crosses)
    3. a number (the target price)

    "tomato price?" → None  (no alert word, no number)
    "nearby mandi"  → None  (no alert word, no number)
    "alert when onion crosses 2000" → {"commodity":"onion","price":2000,"direction":"above"}
    """
    crop = _extract_crop_explicit(msg_lower)
    if not crop:
        return None

    alert_words = [
        "alert",
        "notify",
        "bata",
        "inform",
        "crosses",
        "upar ho",
        "neeche ho",
        "jab",
    ]
    if not any(w in msg_lower for w in alert_words):
        return None

    numbers = re.findall(r"\d+(?:\.\d+)?", msg_lower)
    if not numbers:
        return None

    price = float(numbers[0])
    direction = (
        "below"
        if any(w in msg_lower for w in ["below", "neeche", "less", "gire", "ghate"])
        else "above"
    )
    return {"commodity": crop, "price": price, "direction": direction}


async def _get_price_prediction(crop: str, farmer_id: str) -> str:
    from services.prediction_service import predict_prices
    from services.db import SessionLocal
    from services.market_service import find_best_mandi_for_commodity

    db = SessionLocal()
    try:
        saved = get_farmer_location(farmer_id)
        market = "General"
        if saved:
            mandis = find_best_mandi_for_commodity(
                saved["lat"], saved["lng"], crop, 500, 1, db
            )
            if mandis:
                market = mandis[0]["market"]

        pred = predict_prices(crop, market, db)
    finally:
        db.close()

    if pred.get("error"):
        return f"__DIRECT_REPLY__{pred['error']}\n\nKoi aur madad chahiye? 🌾"

    trend_emoji = {"rising": "📈", "falling": "📉", "stable": "➡️"}.get(
        pred["trend"], ""
    )

    return (
        f"__DIRECT_REPLY__{trend_emoji} *{crop.title()} Price Forecast*\n\n"
        f"Aaj ka bhav  : Rs.*{pred['current_price']}*/quintal\n"
        f"7 din baad   : Rs.*{pred['day_7_price']}*/quintal\n"
        f"Badlaav      : {'+' if pred['change_pct'] > 0 else ''}{pred['change_pct']}%\n\n"
        f"*Salah:* {pred['advice']}\n\n"
        f"Koi aur madad chahiye? 🌾"
    )
