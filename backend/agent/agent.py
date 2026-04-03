# backend/agent/agent.py
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import AsyncGroq

from backend.agent.tools import (
    get_weather,
    get_mandi_price,
    get_treatment,
    get_govt_schemes,
    get_disease_progression,
)
from backend.services.location_state import set_pending_location_action
from backend.db.crud import _get_or_create_farmer, normalize, save_price_alert
from backend.db.database import AsyncSessionLocal

load_dotenv()
client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))


# ─── Language helpers ──────────────────────────────────────────────────────────


def _lang_key(language: str) -> str:
    lang = (language or "Hindi").strip().lower()
    if lang == "english":
        return "english"
    if lang == "kannada":
        return "kannada"
    return "hindi"


def build_system_prompt(language: str = "Hindi") -> str:
    lang = (language or "Hindi").strip()
    return (
        "You are KrishiMitra, a practical farming assistant for Indian farmers.\n"
        f"Reply primarily in {lang} using simple farmer-friendly language.\n"
        "Rules:\n"
        "- Give short, actionable replies.\n"
        "- If user asks mandi/price/location, use provided tool data first.\n"
        "- If disease is discussed, include treatment + likely progression.\n"
        "- Never invent exact government policy numbers.\n"
        "- If location is needed, ask the user to share WhatsApp live location.\n"
        "- Never mention tool names in your reply.\n"
        "- Format replies cleanly.\n"
        "- Always end with: 'Koi aur madad chahiye? 🌾'\n"
    )


# ─── Extraction helpers ────────────────────────────────────────────────────────


def extract_location(message: str) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    patterns = [
        r"(?:in|at|near|around|from)\s+([A-Za-z][A-Za-z\s\-]{2,40})",
        r"(?:mandi|market)\s+(?:in|at|near)\s+([A-Za-z][A-Za-z\s\-]{2,40})",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip(" .,!?:;")
    return None


def extract_crop(message: str) -> str | None:
    text = (message or "").lower()
    crop_aliases = {
        "tomato": ["tomato", "tamatar"],
        "onion": ["onion", "pyaz", "pyaaz"],
        "potato": ["potato", "aloo"],
        "wheat": ["wheat", "gehun", "gehu"],
        "rice": ["rice", "paddy", "dhaan", "dhan"],
        "maize": ["maize", "corn", "makka"],
        "cotton": ["cotton", "kapas"],
        "soyabean": ["soyabean", "soybean", "soya"],
        "groundnut": ["groundnut", "peanut", "mungfali", "moongfali"],
        "chilli": ["chilli", "chili", "mirchi"],
        "cabbage": ["cabbage", "patta gobhi"],
        "cauliflower": ["cauliflower", "gobhi"],
        "brinjal": ["brinjal", "baingan", "eggplant"],
        "ginger": ["ginger", "adrak"],
        "garlic": ["garlic", "lahsun"],
        "mango": ["mango", "aam"],
        "banana": ["banana", "kela"],
        "grape": ["grape", "angoor"],
    }
    for canonical, aliases in crop_aliases.items():
        if any(alias in text for alias in aliases):
            return canonical
    return None


# ─── Weather formatters ────────────────────────────────────────────────────────


def _parse_weather_output(raw: str) -> dict:
    text = (raw or "").strip()
    location = ""
    m = re.search(r"Weather in\s+(.+?):", text, flags=re.IGNORECASE)
    if m:
        location = m.group(1).strip()

    def extract(pattern: str, default: str = "") -> str:
        mm = re.search(pattern, text, flags=re.IGNORECASE)
        return mm.group(1).strip() if mm else default

    return {
        "location": location,
        "temperature": extract(r"Temperature\s*:\s*([^\n]+)"),
        "humidity": extract(r"Humidity\s*:\s*([^\n]+)"),
        "condition": extract(r"Condition\s*:\s*([^\n]+)"),
        "advice": extract(r"Disease Risk\s*:\s*([^\n]+)"),
    }


def _localize_weather_condition(condition: str, language: str) -> str:
    lang = _lang_key(language)
    mapping = {
        "english": {
            "clear sky": "Clear Sky",
            "few clouds": "Few Clouds",
            "scattered clouds": "Scattered Clouds",
            "broken clouds": "Broken Clouds",
            "light rain": "Light Rain",
            "moderate rain": "Moderate Rain",
            "heavy rain": "Heavy Rain",
            "mist": "Mist",
            "haze": "Haze",
        },
        "hindi": {
            "clear sky": "साफ आसमान",
            "few clouds": "हल्के बादल",
            "scattered clouds": "बिखरे बादल",
            "broken clouds": "टूटे बादल",
            "light rain": "हल्की बारिश",
            "moderate rain": "मध्यम बारिश",
            "heavy rain": "भारी बारिश",
            "mist": "कुहासा",
            "haze": "धुंध",
        },
        "kannada": {
            "clear sky": "ಸಾಫ್ ಆಕಾಶ",
            "few clouds": "ಸಾಂದರ್ಭಿಕ ಮೋಡಗಳು",
            "scattered clouds": "ವಿತರಣೆಯ ಮೋಡಗಳು",
            "broken clouds": "ಭಂಗವಾದ ಮೋಡಗಳು",
            "light rain": "ಸೌಮ್ಯ ಮಳೆಯು",
            "moderate rain": "ಮಧ್ಯಮ ಮಳೆಯು",
            "heavy rain": "ಭಾರೀ ಮಳೆಯು",
            "mist": "ಮಂಜು",
            "haze": "ಹೇಸ್",
        },
    }
    return mapping.get(lang, {}).get(condition.lower(), condition)


def _localize_weather_advice(advice: str, language: str) -> str:
    lang = _lang_key(language)
    mapping = {
        "english": {
            "LOW risk — good conditions for spraying": "LOW risk — good conditions for spraying",
            "MEDIUM risk — monitor closely": "MEDIUM risk — monitor closely",
            "HIGH fungal risk — avoid spraying today": "HIGH fungal risk — avoid spraying today",
            "HIGH risk — avoid spraying today": "HIGH risk — avoid spraying today",
        },
        "hindi": {
            "LOW risk — good conditions for spraying": "कम जोखिम — स्प्रे के लिए ठीक मौसम।",
            "MEDIUM risk — monitor closely": "मध्यम जोखिम — ध्यान रखें।",
            "HIGH fungal risk — avoid spraying today": "उच्च फंगल जोखिम — आज स्प्रे न करें।",
            "HIGH risk — avoid spraying today": "उच्च जोखिम — आज स्प्रे न करें।",
        },
        "kannada": {
            "LOW risk — good conditions for spraying": "ಕಡಿಮೆ ಅಪಾಯ — ಸಿಂಪಡಿಸುವಿಕೆಯ ಉತ್ತಮ ಪರಿಸ್ಥಿತಿ.",
            "MEDIUM risk — monitor closely": "ಮಧ್ಯಮ ಅಪಾಯ — ಗಮನವಿಟ್ಟು ವೀಕ್ಷಿಸಿ.",
            "HIGH fungal risk — avoid spraying today": "ಉಚ್ಛ ಫಂಗಲ್ ಅಪಾಯ — ಇವತ್ತು ಸಿಂಪಡಿಸಬೇಡಿ.",
            "HIGH risk — avoid spraying today": "ಉಚ್ಛ ಅಪಾಯ — ಇವತ್ತು ಸಿಂಪಡಿಸಬೇಡಿ.",
        },
    }
    return mapping.get(lang, {}).get(advice, advice)


def _format_weather_direct(raw: str, language: str) -> str:
    data = _parse_weather_output(raw)
    lang = _lang_key(language)
    location = data["location"] or "your area"
    temp = data["temperature"] or "-"
    humidity = data["humidity"] or "-"
    condition = _localize_weather_condition(data["condition"] or "-", language)
    advice = _localize_weather_advice(data["advice"] or "-", language)

    if lang == "english":
        return (
            f"Weather in {location}:\n"
            f"Temperature: {temp}\n"
            f"Humidity: {humidity}\n"
            f"Condition: {condition}\n"
            f"Advice: {advice}"
        )
    if lang == "kannada":
        return (
            f"{location} ನಲ್ಲಿ ಹವಾಮಾನ:\n"
            f"ತಾಪಮಾನ: {temp}\n"
            f"ಆರ್ದ್ರತೆ: {humidity}\n"
            f"ಪರಿಸ್ಥಿತಿ: {condition}\n"
            f"ಸಲಹೆ: {advice}"
        )
    return (
        f"{location} — मौसम:\n"
        f"तापमान: {temp}\n"
        f"नमी: {humidity}\n"
        f"स्थिति: {condition}\n"
        f"सलाह: {advice}"
    )


# ─── Prediction formatters ─────────────────────────────────────────────────────


def _localize_trend(trend: str, language: str) -> str:
    lang = _lang_key(language)
    trend = (trend or "").strip().lower()
    mapping = {
        "english": {"rising": "rising", "falling": "falling", "stable": "stable"},
        "hindi": {"rising": "बढ़ता हुआ", "falling": "घटता हुआ", "stable": "स्थिर"},
        "kannada": {"rising": "ಏರಿಕೆ", "falling": "ಇಳಿಕೆ", "stable": "ಸ್ಥಿರ"},
    }
    return mapping[lang].get(trend, trend or "-")


def _localize_prediction_advice(advice: str, trend: str, language: str) -> str:
    lang = _lang_key(language)
    trend = (trend or "").strip().lower()
    if lang == "english":
        return advice
    if lang == "kannada":
        if trend == "rising":
            return "ಬೆಲೆ ಏರಿಕೆಯಾಗುವ ಸಾಧ್ಯತೆ ಇದೆ — ತಕ್ಷಣ ಮಾರದೇ ಸ್ವಲ್ಪ ಕಾಯಿರಿ."
        if trend == "falling":
            return "ಬೆಲೆ ಇಳಿಯುವ ಸಾಧ್ಯತೆ ಇದೆ — ಈಗ ಮಾರಾಟವನ್ನು ಪರಿಗಣಿಸಿ."
        return "ಬೆಲೆ ಸ್ಥಿರವಾಗಿರಬಹುದು — ನಿಮ್ಮ ಅನುಕೂಲಕ್ಕೆ ಮಾರಬಹುದು."
    if trend == "rising":
        return "भाव बढ़ने की संभावना है — थोड़ा इंतज़ार कर सकते हैं।"
    if trend == "falling":
        return "भाव गिरने की संभावना है — अभी बेचने पर विचार करें।"
    return "भाव लगभग स्थिर रह सकते हैं — अपनी सुविधा से बेचें।"


def _format_prediction_direct(pred: dict, crop: str, language: str) -> str:
    lang = _lang_key(language)
    trend = _localize_trend(pred.get("trend", ""), language)
    advice = _localize_prediction_advice(
        pred.get("advice", ""), pred.get("trend", ""), language
    )
    current_price = pred.get("current_price", "-")
    day_7_price = pred.get("day_7_price", "-")
    change_pct = pred.get("change_pct", 0)

    if lang == "english":
        return (
            f"{crop.title()} price forecast:\n"
            f"Current: Rs.{current_price}/qtl\n"
            f"7-day trend: {trend} ({change_pct:+}%)\n"
            f"Day-7 estimate: Rs.{day_7_price}/qtl\n"
            f"Advice: {advice}"
        )
    if lang == "kannada":
        return (
            f"{crop.title()} ಬೆಲೆ ಅಂದಾಜು:\n"
            f"ಈಗಿನ ಬೆಲೆ: Rs.{current_price}/ಕ್ವಿಂಟಲ್\n"
            f"7 ದಿನಗಳ ಧೋರಣೆ: {trend} ({change_pct:+}%)\n"
            f"7ನೇ ದಿನ ಅಂದಾಜು: Rs.{day_7_price}/ಕ್ವಿಂಟಲ್\n"
            f"ಸಲಹೆ: {advice}"
        )
    return (
        f"{crop.title()} भाव अनुमान:\n"
        f"अभी मूल्य: Rs.{current_price}/क्विंटल\n"
        f"7 दिन का रुझान: {trend} ({change_pct:+}%)\n"
        f"7वें दिन अनुमान: Rs.{day_7_price}/क्विंटल\n"
        f"सलाह: {advice}"
    )


# ─── Alert formatter ───────────────────────────────────────────────────────────


def _format_alert_direct(
    crop: str, target: float, direction: str, created: bool, language: str
) -> str:
    lang = _lang_key(language)
    dir_word = {
        "english": {"above": "above", "below": "below"},
        "hindi": {"above": "ऊपर", "below": "नीचे"},
        "kannada": {"above": "ಮೇಲೆ", "below": "ಕೆಳಗೆ"},
    }[lang].get(direction, direction)

    if lang == "english":
        if created:
            return (
                f"Price alert set for {crop.title()} at Rs.{target:.0f} ({dir_word})."
            )
        return (
            f"Alert already active for {crop.title()} at Rs.{target:.0f} ({dir_word})."
        )
    if lang == "kannada":
        if created:
            return f"{crop.title()} ಗೆ Rs.{target:.0f} ({dir_word}) ಬೆಲೆ ಅಲರ್ಟ್ ಸೆಟ್ ಮಾಡಲಾಗಿದೆ."
        return f"{crop.title()} ಗೆ Rs.{target:.0f} ({dir_word}) ಅಲರ್ಟ್ ಈಗಾಗಲೇ ಸಕ್ರಿಯವಾಗಿದೆ."
    if created:
        return f"भाव अलर्ट सेट हो गया: {crop.title()} Rs.{target:.0f} ({dir_word})."
    return f"यह भाव अलर्ट पहले से सक्रिय है: {crop.title()} Rs.{target:.0f} ({dir_word})."


# ─── Location request message ──────────────────────────────────────────────────


def _location_request_message(language: str) -> str:
    lang = _lang_key(language)
    if lang == "english":
        return (
            "To give accurate mandi rates, please share your live location.\n"
            "WhatsApp: Attachment → Location → Send current location."
        )
    if lang == "kannada":
        return (
            "ಸರಿಯಾದ ಮಂಡಿ ದರಗಳನ್ನು ನೀಡಲು ದಯವಿಟ್ಟು ನಿಮ್ಮ ಲೈವ್ ಲೊಕೇಶನ್ ಹಂಚಿಕೊಳ್ಳಿ.\n"
            "WhatsApp: Attachment → Location → Send current location."
        )
    return (
        "Mandi ke sahi rates dene ke liye apni live location share karein.\n"
        "WhatsApp: Attachment → Location → Send current location."
    )


# ─── Tool orchestration ────────────────────────────────────────────────────────


async def _saved_farmer_coordinates(farmer_id: str) -> dict | None:
    pid = normalize((farmer_id or "").replace("whatsapp:", "").strip()) or ""
    db = AsyncSessionLocal()
    try:
        farmer, _ = await _get_or_create_farmer(db, pid)
        if farmer and farmer.lat is not None and farmer.lng is not None:
            return {"lat": float(farmer.lat), "lng": float(farmer.lng)}
    finally:
        await db.close()
    return None


async def use_tools(
    farmer_id: str,
    message: str,
    disease_result: dict | None = None,
    language: str = "Hindi",
) -> tuple[str | None, str | None]:

    text = (message or "").strip()
    lower = text.lower()

    # ── 1. Price alert ────────────────────────────────────
    alert_keywords = ["alert", "notify", "batana", "batana jab", "when price"]
    if any(k in lower for k in alert_keywords):
        crop = extract_crop(text)
        m = re.search(
            r"(above|below|upar|neeche|greater than|less than)"
            r"\s*(?:rs\.?\s*)?(\d+(?:\.\d+)?)",
            lower,
        )
        if crop and m:
            direction_raw = m.group(1)
            direction = (
                "above"
                if direction_raw in {"above", "upar", "greater than"}
                else "below"
            )
            target = float(m.group(2))
            db = AsyncSessionLocal()
            try:
                result = await save_price_alert(db, farmer_id, crop, target, direction)
            finally:
                await db.close()
            return "__DIRECT_REPLY__", _format_alert_direct(
                crop=crop,
                target=target,
                direction=direction,
                created=result.get("created", False),
                language=language,
            )

    # ── 2. Govt schemes ───────────────────────────────────
    if any(
        k in lower for k in ["scheme", "yojana", "subsidy", "government help", "govt"]
    ):
        location = extract_location(text) or "India"
        return "__DIRECT_REPLY__", get_govt_schemes(location)

    # ── 3. Disease / treatment ────────────────────────────
    disease_keywords = ["disease", "blight", "rust", "spot", "infection", "pest"]
    if disease_result or any(k in lower for k in disease_keywords):
        disease_name = None
        if disease_result and isinstance(disease_result, dict):
            disease_name = disease_result.get("disease") or disease_result.get("label")
        if not disease_name:
            disease_name = text
        treatment = get_treatment(str(disease_name))
        progression = get_disease_progression(str(disease_name))
        return "__DIRECT_REPLY__", f"{treatment}\n\n{progression}"

    # ── 4. Price prediction ───────────────────────────────
    if any(k in lower for k in ["predict", "prediction", "next 7 days", "forecast"]):
        crop = extract_crop(text)
        if not crop:
            lang = _lang_key(language)
            msg = {
                "english": "Please send the crop name for prediction.",
                "kannada": "ಭವಿಷ್ಯವಾಣಿಗಾಗಿ ಬೆಳೆ ಹೆಸರನ್ನು ಕಳುಹಿಸಿ.",
                "hindi": "Prediction ke liye crop name bhejiye, jaise: Tomato.",
            }
            return "__DIRECT_REPLY__", msg.get(lang, msg["hindi"])

        from backend.services.prediction_service import predict_prices_async

        market = extract_location(text) or "default"
        db = AsyncSessionLocal()
        try:
            pred = await predict_prices_async(crop, market, db)
        finally:
            await db.close()

        if pred.get("error"):
            return "__DIRECT_REPLY__", pred["error"]

        return "__DIRECT_REPLY__", _format_prediction_direct(pred, crop, language)

    # ── 5. Mandi / market / price ─────────────────────────
    mandi_keywords = [
        "mandi",
        "market",
        "price",
        "bhav",
        "rate",
        "sell",
        "nearby",
        "nearest",
        "paas",
        "kahan",
        "markets",
        "where to sell",
        "kahan bechu",
        "daam",
        "keemat",
    ]
    if any(k in lower for k in mandi_keywords):
        from backend.agent.mandi_tool_update import (
            get_mandis_for_city,
            get_mandis_for_gps,
        )

        crop = extract_crop(text)
        city = extract_location(text)
        saved = await _saved_farmer_coordinates(farmer_id)

        # Has GPS → use exact coordinate flow
        if saved and saved.get("lat") is not None:
            reply = await get_mandis_for_gps(
                lat=float(saved["lat"]),
                lng=float(saved["lng"]),
                commodity=crop,
                farmer_id=farmer_id,
                language=language,
            )
            return "__DIRECT_REPLY__", reply

        # Has city name → use city-based flow
        if city:
            reply = await get_mandis_for_city(
                city=city,
                commodity=crop,
                farmer_id=farmer_id,
                language=language,
            )
            return "__DIRECT_REPLY__", reply

        # No location → ask for GPS
        await set_pending_location_action(
            phone=farmer_id,
            commodity=crop,
            language=language,
            reason="mandi",
        )
        return "__LOCATION_REQUESTED__", None

    # ── 6. Weather ────────────────────────────────────────
    weather_keywords = [
        "weather",
        "mausam",
        "temperature",
        "humidity",
        "barish",
        "rain",
        "spray",
        "baarish",
    ]
    if any(k in lower for k in weather_keywords):
        location = extract_location(text) or "India"
        raw_weather = get_weather(location)
        return "__DIRECT_REPLY__", _format_weather_direct(raw_weather, language)

    return None, None


# ─── Main entry point ──────────────────────────────────────────────────────────


async def process_message(
    farmer_id: str,
    message: str,
    language: str = "Hindi",
    history: list | None = None,
    disease_result: dict | None = None,
) -> str:
    try:
        text = (message or "").strip()
        lower = text.lower()
        if "follow up" in message.lower() or "track this" in message.lower():
            from backend.scheduler import schedule_followup

            if disease_result and isinstance(disease_result, dict):
                disease_name = disease_result.get("disease", "unknown")
                severity = disease_result.get("severity", {})
                bbox_pct = (
                    severity.get("percentage", 30) if isinstance(severity, dict) else 30
                )

                schedule_followup(
                    phone=farmer_id,
                    farmer_name="Farmer",
                    disease_name=disease_name,
                    bbox_pct=bbox_pct,
                )

                return "✅ Follow-up scheduled in 3 days. I will check back with you."
        # ── Pagination: "more" / "aur dikhao" ────────────
        if any(token in lower for token in ["more", "aur", "aur dikhao"]):
            from backend.agent.mandi_tool_update import handle_more, has_pending_page

            if has_pending_page(farmer_id):
                more_reply = await handle_more(farmer_id)
                if more_reply:
                    return more_reply

        # ── Build disease context ─────────────────────────
        extra_context: list[str] = []
        if disease_result and isinstance(disease_result, dict):
            d_name = disease_result.get("disease") or disease_result.get("label")
            d_conf = disease_result.get("confidence")
            d_sev = disease_result.get("severity", {})
            d_urg = disease_result.get("urgency", "")
            d_prog = disease_result.get("progression", {})

            if d_name:
                ctx = f"CROP PHOTO DIAGNOSIS:\nDisease: {d_name}"
                if d_conf:
                    ctx += f"\nConfidence: {d_conf}"
                if d_sev:
                    ctx += (
                        f"\nSeverity: {d_sev.get('level', 'Unknown')} — "
                        f"{d_sev.get('description', '')}"
                    )
                if d_urg:
                    ctx += f"\nUrgency: {d_urg}"
                if d_prog:
                    ctx += (
                        f"\nIf untreated 7 days: "
                        f"{d_prog.get('day_7_spread', '?')} crop affected"
                    )
                extra_context.append(ctx)

        # ── Tool calls ────────────────────────────────────
        tool_status, tool_payload = await use_tools(
            farmer_id=farmer_id,
            message=text,
            disease_result=disease_result,
            language=language,
        )

        # Direct reply from tool
        if tool_status == "__DIRECT_REPLY__" and tool_payload:
            return tool_payload

        # Location needed
        if tool_status == "__LOCATION_REQUESTED__":
            return _location_request_message(language)

        # Tool data to pass to LLM
        if tool_payload:
            extra_context.append(str(tool_payload))

        # ── LLM fallback ──────────────────────────────────
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": build_system_prompt(language)}
        ]

        for item in history or []:
            role = item.get("role")
            content = item.get("content")
            if (
                role in {"user", "assistant"}
                and isinstance(content, str)
                and content.strip()
            ):
                messages.append({"role": role, "content": content.strip()})

        user_content = text or "Hello"
        if extra_context:
            user_content = f"{user_content}\n\nAdditional context:\n" + "\n".join(
                extra_context
            )
        messages.append({"role": "user", "content": user_content})

        resp = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=500,
        )
        final = (resp.choices[0].message.content or "").strip()
        return final or "Maaf kijiye, jawab generate nahi ho paya. Dobara poochiye."

    except Exception as exc:
        print(f"[agent.process_message] error: {exc}")
        return "Maaf kijiye, technical issue aa gaya. Thodi der baad phir poochiye."
