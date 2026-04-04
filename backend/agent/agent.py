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
    get_nearby_mandis,
)
from services.location_state import _pending_location
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
# Fallback to backend/.env when running from project root.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
from farmer_store import get_farmer_location, get_farmer_language, normalize_phone
from services.market_service import extract_state_filter
client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

memory_store = {}


def get_history(farmer_id: str) -> list:
    if farmer_id not in memory_store:
        memory_store[farmer_id] = []
    return memory_store[farmer_id]


def save_message(farmer_id: str, role: str, content: str):
    history = get_history(farmer_id)
    history.append({"role": role, "content": content})
    if len(history) > 10:
        memory_store[farmer_id] = history[-10:]


SYSTEM_PROMPT = """
You are KrishiMitra, a friendly AI farming assistant for Indian farmers.

IMPORTANT: Never mention tool names like get_treatment or get_nearby_mandis
in your reply. Just use the data they return naturally in your response.

When farmer sends crop photo with diagnosis:
1. Tell disease name and severity clearly
2. Give specific treatment with medicine names and dosage
3. Warn how fast it spreads if untreated
4. Give urgency level
5. For chemical names, add a short line with example online search (Amazon.in / Ugaoo / local agri store) using the product name — do not invent fake URLs

When farmer asks about prices:
1. Give current rates
2. Suggest nearest mandi to sell

When farmer asks about schemes:
1. List schemes with how to apply

Rules:
- Always reply in SAME language as farmer
- Hindi → Hindi reply
- English → English reply  
- Keep replies SHORT and PRACTICAL
- Never mention tool names in reply
-format the replays in clean way
- Always end with: 'Koi aur madad chahiye? 🌾'
"""


async def process_message(
    farmer_id: str, message: str, disease_result: dict = None
) -> str:
    try:
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
                f"Severity  : {severity.get('level', 'Unknown')} — {severity.get('description', '')}\n"
                f"Urgency   : {urgency}\n"
            )
            if prog:
                context += (
                    f"If untreated: {prog.get('day_7_spread', '?')} crop affected in 7 days\n"
                    f"Warning: {prog.get('warning', '')}\n"
                )
            message = f"{context}\nFarmer message: {message or 'Please help me'}"

        history = get_history(farmer_id)
        system_prompt = SYSTEM_PROMPT
        pref = get_farmer_language(normalize_phone(farmer_id))
        if pref:
            lang_names = {"hindi": "Hindi", "kannada": "Kannada", "english": "English"}
            system_prompt += (
                f"\n\nFarmer registered language preference: {lang_names.get(pref, pref)}. "
                "Reply in this language."
            )
        messages = (
            [{"role": "system", "content": system_prompt}]
            + history
            + [{"role": "user", "content": message}]
        )

        tool_result = await use_tools(message, disease_result, farmer_id)

        # Sentinel: location needed
        if tool_result == "__LOCATION_REQUESTED__":
            msg_lower = message.lower()
            explicit_crop = None
            for c in ["tomato","potato","onion","wheat","rice","cotton","corn","grape","pepper","mango","banana"]:
                if c in msg_lower:
                    explicit_crop = c
                    break
            crop_str = f"*{explicit_crop}*" if explicit_crop else "mandis"
            return (
                f"Aapki location save karni hai taaki agle baar seedha jawab de sakoon!\n"
                f"Please apni *WhatsApp location share karein* 📍\n\n"
                f"(Attachment > Location > Send Current Location)\n\n"
                f"Koi aur madad chahiye? 🌾"
            )

        # Sentinel: mandi result already computed
        if tool_result and tool_result.startswith("__DIRECT_REPLY__"):
            return tool_result.replace("__DIRECT_REPLY__", "", 1)

        # Normal LLM flow
        if tool_result:
            messages.append({"role": "user", "content": f"Additional data:\n{tool_result}"})

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
        return f"Sorry, please try again. Error: {str(e)}"


# Pass farmer_id into use_tools
async def use_tools(message: str, disease_result: dict = None, farmer_id: str = None) -> str:
    msg_lower = message.lower()
    results = []

    # Auto-use treatment tool if disease detected
    if disease_result and not disease_result.get("error"):
        disease = disease_result.get("disease", "")
        if disease and disease != "Could not analyze":
            results.append(get_treatment.run(disease))
            results.append(get_disease_progression.run(disease))

    # Weather tool
    if any(w in msg_lower for w in ["weather", "rain", "spray", "mausam", "barish", "humid"]):
        location = extract_location(message)
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
    if any(w in msg_lower for w in ["predict", "forecast", "rise", "fall",
                                     "badhega", "ghategaa", "trend", "future"]):
        crop = _extract_crop_explicit(msg_lower)
        if crop:
            return await _get_price_prediction(crop, farmer_id)

    # Price tool — keep this separate from nearby
    if any(w in msg_lower for w in ["price", "rate", "bhav"]):
        crop = extract_crop(message)
        state_f = extract_state_filter(message)
        if state_f:
            from services.db import SessionLocal
            from services.market_service import get_latest_prices

            db = SessionLocal()
            try:
                rows = get_latest_prices(crop, state_f, db)
            finally:
                db.close()
            if rows:
                lines = f"*{state_f}* — *{crop.title()}* bhav:\n\n"
                for r in rows[:5]:
                    lines += f"• {r['market']}: Rs.{r['modal_price']}/q\n"
                return (
                    f"__DIRECT_REPLY__{lines}\n"
                    f"Koi aur madad chahiye? 🌾"
                )
        results.append(get_mandi_price.run(crop))

    # Nearby mandi block — replace entirely
    if any(w in msg_lower for w in ["nearby", "nearest", "closest", "paas", "kahan", "mandi", "sell", "market"]):
        explicit_crop = None
        for c in ["tomato","potato","onion","wheat","rice","cotton","corn","grape","pepper","mango","banana"]:
            if c in msg_lower:
                explicit_crop = c
                break

        state_f = extract_state_filter(message)
        saved = get_farmer_location(farmer_id)
        if saved:
            from services.whatsapp_service import handle_location_for_mandi
            mandi_reply = await handle_location_for_mandi(
                phone=farmer_id,
                lat=saved["lat"],
                lng=saved["lng"],
                commodity=explicit_crop,
                state_filter=state_f,
            )
            return f"__DIRECT_REPLY__{mandi_reply}"  # ← inside if saved

        # No saved location — ask for it
        _pending_location[farmer_id] = {
            "waiting": "mandi",
            "commodity": explicit_crop,
            "state_filter": state_f,
        }
        return "__LOCATION_REQUESTED__"

    # Schemes
    if any(w in msg_lower for w in ["scheme", "subsidy", "insurance", "yojana", "sarkar"]):
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
    for c in ["tomato","potato","onion","wheat","rice","cotton",
              "corn","grape","pepper","mango","banana"]:
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

    alert_words = ["alert", "notify", "bata", "inform", "crosses",
                   "upar ho", "neeche ho", "jab"]
    if not any(w in msg_lower for w in alert_words):
        return None

    numbers = re.findall(r'\d+(?:\.\d+)?', msg_lower)
    if not numbers:
        return None

    price     = float(numbers[0])
    direction = "below" if any(w in msg_lower for w in
                               ["below", "neeche", "less", "gire", "ghate"]) else "above"
    return {"commodity": crop, "price": price, "direction": direction}


async def _get_price_prediction(crop: str, farmer_id: str) -> str:
    from services.prediction_service import predict_prices
    from services.db import SessionLocal
    from services.market_service import find_best_mandi_for_commodity

    db = SessionLocal()
    try:
        saved  = get_farmer_location(farmer_id)
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

    trend_emoji = {"rising": "📈", "falling": "📉", "stable": "➡️"}.get(pred["trend"], "")

    return (
        f"__DIRECT_REPLY__{trend_emoji} *{crop.title()} Price Forecast*\n\n"
        f"Aaj ka bhav  : Rs.*{pred['current_price']}*/quintal\n"
        f"7 din baad   : Rs.*{pred['day_7_price']}*/quintal\n"
        f"Badlaav      : {'+' if pred['change_pct'] > 0 else ''}{pred['change_pct']}%\n\n"
        f"*Salah:* {pred['advice']}\n\n"
        f"Koi aur madad chahiye? 🌾"
    )