import asyncio
import os
import uuid
import httpx
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text
from requests.auth import HTTPBasicAuth
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from backend.agent.agent import process_message
from backend.agent.diagnose import diagnose_image
from backend.agent.guardrails import check_message, check_image
from backend.services.location_state import clear_pending_location_action
from backend.services.market_service import (
    find_best_mandi_for_commodity,
)
from backend.db.database import AsyncSessionLocal
from backend.db.crud import (
    _get_or_create_farmer,
    add_disease,
    append_message_pair,
    get_recent_messages,
    set_farmer_language,
    set_farmer_location_coords,
    upsert_farmer_profile,
    reserve_inbound_message,
    finalize_inbound_message,
    fail_inbound_message,
)

load_dotenv()

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
FROM_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

twilio_client = Client(ACCOUNT_SID, AUTH_TOKEN)
TEMP_DIR = tempfile.gettempdir()

AGENT_DIR = Path(__file__).resolve().parent.parent / "agent"
_MODEL_DIR = AGENT_DIR / "model"
if not (_MODEL_DIR / "classifier.onnx").exists():
    _MODEL_DIR = AGENT_DIR / "models"

CLASSIFIER_PATH = str(_MODEL_DIR / "classifier.onnx")
DETECTOR_PATH = str(_MODEL_DIR / "detector.onnx")

LANGUAGE_MENU = (
    "🌾 *KrishiMitra mein aapka swagat hai!*\n"
    "ಕೃಷಿಮಿತ್ರಕ್ಕೆ ಸ್ವಾಗತ! / Welcome to KrishiMitra!\n\n"
    "Apni bhasha chunein:\n"
    "ನಿಮ್ಮ ಭಾಷೆ ಆಯ್ಕೆ ಮಾಡಿ:\n"
    "Choose your language:\n\n"
    "1️⃣  हिंदी (Hindi)\n"
    "2️⃣  ಕನ್ನಡ (Kannada)\n"
    "3️⃣  English\n\n"
    "*1, 2 ya 3 reply karein* / *1, 2 ಅಥವಾ 3 ಉತ್ತರಿಸಿ* / *Reply with 1, 2 or 3*"
)

LANGUAGE_MAP = {"1": "Hindi", "2": "Kannada", "3": "English"}

LANGUAGE_CONFIRM = {
    "Hindi": "✅ भाषा सेट हो गई: *हिंदी* 🌾\nअब अपना सवाल पूछें!",
    "Kannada": "✅ ಭಾಷೆ ಸೆಟ್ ಆಗಿದೆ: *ಕನ್ನಡ* 🌾\nಈಗ ನಿಮ್ಮ ಪ್ರಶ್ನೆ ಕೇಳಿ!",
    "English": "✅ Language set: *English* 🌾\nNow ask your question!",
}

LOCATION_PROMPT = """📍 To get accurate mandi prices, please share your location.

👉 How to send location:
• Tap 📎 (attachment icon)
• Select "Location"
• Send your current location

🌾 This helps me find the nearest market prices for you."""

NO_DISEASE_REPLY = """🌿 No disease detected in the image.

✅ Your crop looks healthy.

💡 Tips:
• Keep monitoring regularly
• Maintain proper watering
• Ensure good sunlight and spacing

📸 If you still suspect an issue, send another clear photo.

🌾 Need help? I'm here!"""

LOW_CONFIDENCE_REPLY = """🤔 I'm not fully sure about the disease.

📸 Please send:
• a clearer image
• close-up of affected leaves

🌾 I'll help you better!"""

MANDI_ASK_CROP = (
    "🌾 Please mention the crop (e.g., tomato, rice) to get mandi prices."
)

PRICE_ASK_CROP = (
    "🌾 Please tell me which crop you want prices for (e.g., tomato, rice)."
)

MANDI_ONLY_FOOTER = """🌾 Ask like:
'tomato price' to get crop prices"""

# Approximate coords for text-only location (mandi flow)
CITY_COORDS = {
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "kolar": (13.1362, 78.1296),
    "mysore": (12.2958, 76.6394),
    "mysuru": (12.2958, 76.6394),
    "pune": (18.5204, 73.8567),
    "mumbai": (19.0760, 72.8777),
    "delhi": (28.6139, 77.2090),
    "hyderabad": (17.3850, 78.4867),
    "nashik": (19.9975, 73.7898),
    "nagpur": (21.1458, 79.0882),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "ahmedabad": (23.0225, 72.5714),
    "jaipur": (26.9124, 75.7873),
    "lucknow": (26.8467, 80.9462),
    "patna": (25.5941, 85.1376),
    "bhopal": (23.2599, 77.4126),
    "indore": (22.7196, 75.8577),
    "chandigarh": (30.7333, 76.7794),
    "kochi": (9.9312, 76.2673),
    "salem": (11.6643, 78.1460),
}


def _city_coords_key(city: str | None) -> str | None:
    if not city:
        return None
    c = city.lower().strip()
    if c in CITY_COORDS:
        return c
    if c == "bengaluru":
        return "bangalore"
    if c == "mysuru":
        return "mysore"
    return None


def _lat_lng_from_text_city(text_city: str | None) -> tuple[float | None, float | None]:
    key = _city_coords_key(text_city)
    if not key:
        return None, None
    coords = CITY_COORDS.get(key)
    if not coords:
        return None, None
    return float(coords[0]), float(coords[1])


def parse_confidence(val):
    try:
        
        return int(float(str(val).replace("%", "")))
    except (TypeError, ValueError):
        return 30


def extract_location(text: str) -> str | None:
    if not (text or "").strip():
        return None
    lower = (text or "").lower()
    cities = [
        "salem",
        "bengaluru",
        "bangalore",
        "mysuru",
        "mysore",
        "chennai",
        "kolar",
        "pune",
        "mumbai",
        "delhi",
        "hyderabad",
        "nashik",
        "nagpur",
        "kolkata",
        "ahmedabad",
        "jaipur",
        "lucknow",
        "patna",
        "bhopal",
        "indore",
        "chandigarh",
        "kochi",
    ]
    for city in cities:
        if city in lower:
            return city
    return None


def extract_crop_name(text: str) -> str | None:
    crop_aliases = {
        "tomato": ["tomato", "tamatar"],
        "rice": ["rice", "paddy"],
        "wheat": ["wheat", "gehu"],
        "onion": ["onion", "pyaz"],
        "maize": ["maize", "corn"],
        "chilli": ["chilli", "chili"],
    }

    t = (text or "").lower()

    for crop, aliases in crop_aliases.items():
        for word in aliases:
            if word in t:
                return crop

    extra = [
        "potato",
        "cotton",
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
        "groundnut",
        "soybean",
    ]
    for crop in extra:
        if crop in t:
            return crop
    return None


def format_disease_response(disease_result: dict) -> str:
    from backend.agent.tools import get_treatment

    disease = disease_result.get("disease", "Unknown disease")
    confidence = disease_result.get("confidence", "0%")

    try:
        confidence_val = int(float(str(confidence).replace("%", "")))
    except (TypeError, ValueError):
        confidence_val = 0

    if confidence_val > 75:
        severity = "🔴 High"
    elif confidence_val > 40:
        severity = "🟡 Moderate"
    else:
        severity = "🟢 Low"

    treatment = disease_result.get("treatment")
    if not treatment or treatment == "No treatment available":
        treatment = get_treatment(str(disease)) or "No treatment available"

    return f"""🦠 Disease Detected: *{disease}*

📊 Severity: {severity} ({confidence})

💊 Treatment:
{treatment}

⚠️ What to do:
• Start treatment immediately if severity is high
• Monitor crop daily
• Avoid excess moisture

📸 Send another photo in 2-3 days to track progress.

🌾 Need help? Just ask!"""


def _format_smart_mandi_text(results: list, commodity: str, language: str) -> str:
    lang = (language or "Hindi").strip().lower()
    lines = []
    for i, m in enumerate(results, 1):
        dist = m.get("distance", m.get("distance_km", "?"))
        lines.append(
            f"{i}. *{m['market']}* - Rs.{m.get('modal_price', 0)}/q (~{dist} km)"
        )
    body = "\n".join(lines)
    if lang == "english":
        return f"*Mandi prices for {commodity.title()}:*\n\n{body}\n\nNeed anything else? 🌾"
    if lang == "kannada":
        return f"*{commodity.title()} ಮಂಡಿ ದರ:*\n\n{body}\n\nಇನ್ನೇನಾದರೂ ಬೇಕೇ? 🌾"
    return f"*{commodity.title()} mandi bhav:*\n\n{body}\n\nAur madad? 🌾"


def _twiml(text: str) -> str:
    twiml = MessagingResponse()
    twiml.message((text or "")[:1599])
    return str(twiml)


async def extract_farmer_data(message: str) -> dict:
    text = (message or "").strip()
    if not text:
        return {}

    data = {}
    lower = text.lower()

    crop_keywords = [
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
    for crop in crop_keywords:
        if crop in lower:
            data["crop"] = crop
            break

    city_candidates = [
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
        "kochi",
        "kolar",
        "mysore",
        "mysuru",
    ]
    for city in city_candidates:
        if city in lower:
            data["location"] = city
            break

    return data


async def _farmer_llm_context(phone: str) -> dict:
    db = AsyncSessionLocal()
    try:
        fam, _ = await _get_or_create_farmer(db, phone)
        if not fam:
            return {}
        crop = fam.crops[0] if fam.crops else None
        return {
            "crop": crop,
            "location": fam.location,
            "last_disease": fam.last_disease,
        }
    finally:
        await db.close()


async def _finalize_and_return(
    provider_message_id: str | None,
    response_xml: str,
) -> str:
    db = AsyncSessionLocal()
    try:
        await finalize_inbound_message(db, provider_message_id, response_xml)
    finally:
        await db.close()
    return response_xml


async def _fail_and_return(
    provider_message_id: str | None,
    error: str,
    fallback_text: str,
) -> str:
    db = AsyncSessionLocal()
    try:
        await fail_inbound_message(db, provider_message_id, error)
    finally:
        await db.close()
    return _twiml(fallback_text)


async def handle_incoming_message(form_data: dict) -> str:
    phone = form_data.get("From", "").replace("whatsapp:", "").strip().lower()
    body = (form_data.get("Body") or "").strip()
    num_media = int(form_data.get("NumMedia", 0) or 0)
    media_url = form_data.get("MediaUrl0")
    content_type = form_data.get("MediaContentType0")
    latitude = form_data.get("Latitude")
    longitude = form_data.get("Longitude")
    provider_message_id = form_data.get("MessageSid")

    if not phone:
        return _twiml("Invalid sender. Please try again.")

    message_lower = (body or "").lower()

    db = AsyncSessionLocal()
    try:
        inbound = await reserve_inbound_message(
            db,
            provider_message_id=provider_message_id,
            phone=phone,
            body=body,
        )
    finally:
        await db.close()

    if inbound["state"] == "duplicate_done":
        return inbound["response_xml"]

    if inbound["state"] == "duplicate_inflight":
        return _twiml("Processing... 🌾")

    if "follow up" in message_lower:
        from backend.scheduler import schedule_followup

        schedule_followup(
            phone=phone,
            farmer_name="Farmer",
            disease_name="recent",
            bbox_pct=30,
        )

        return await _finalize_and_return(
            provider_message_id,
            _twiml("✅ Follow-up scheduled."),
        )

    farmer_language: str | None = None
    try:
        db = AsyncSessionLocal()
        try:
            farmer, _ = await _get_or_create_farmer(db, phone)
            farmer_language = farmer.language if farmer and farmer.language else None
        finally:
            await db.close()

        language_menu = _twiml(LANGUAGE_MENU)

        if latitude and longitude:
            try:
                lat = float(latitude)
                lng = float(longitude)
            except ValueError:
                response_xml = _twiml(
                    "Invalid location received. Please share location again."
                )
                return await _finalize_and_return(provider_message_id, response_xml)

            db = AsyncSessionLocal()
            try:
                await set_farmer_location_coords(db, phone, lat, lng)
            finally:
                await db.close()

            pending = await clear_pending_location_action(phone)
            chosen_language = (
                (pending or {}).get("language") or farmer_language or "Hindi"
            )

            if pending:
                reply = await handle_location_for_mandi(
                    phone=phone,
                    lat=lat,
                    lng=lng,
                    commodity=pending.get("commodity"),
                    language=chosen_language,
                )
                return await _finalize_and_return(provider_message_id, _twiml(reply))

            if chosen_language.strip().lower() == "english":
                response_xml = _twiml(
                    "Location saved! Now you can ask about mandi or market prices. 📍🌾"
                )
                return await _finalize_and_return(provider_message_id, response_xml)

            if chosen_language.strip().lower() == "kannada":
                response_xml = _twiml(
                    "ಲೊಕೇಶನ್ ಉಳಿಸಲಾಗಿದೆ! ಈಗ ನೀವು ಮಂಡಿ ಅಥವಾ ಮಾರುಕಟ್ಟೆ ಬೆಲೆ ಬಗ್ಗೆ ಕೇಳಬಹುದು. 📍🌾"
                )
                return await _finalize_and_return(provider_message_id, response_xml)

            response_xml = _twiml(
                "Location saved! Ab aap mandi ya market ke baare mein pooch sakte hain. 📍🌾"
            )
            return await _finalize_and_return(provider_message_id, response_xml)

        if not farmer_language:
            choice = body.strip()
            selected = LANGUAGE_MAP.get(choice)
            if not selected:
                return await _finalize_and_return(provider_message_id, language_menu)

            db = AsyncSessionLocal()
            try:
                await set_farmer_language(db, phone, selected)
            finally:
                await db.close()

            farmer_language = selected

            response_xml = _twiml(LANGUAGE_CONFIRM[selected])
            return await _finalize_and_return(provider_message_id, response_xml)

        msg_check = check_message(body)
        if not msg_check.allowed:
            response_xml = _twiml(msg_check.reply)
            return await _finalize_and_return(provider_message_id, response_xml)

        if not num_media and "treatment" in message_lower:
            db_tr = AsyncSessionLocal()
            try:
                fam_tr, _ = await _get_or_create_farmer(db_tr, phone)
            finally:
                await db_tr.close()
            from backend.agent.tools import get_treatment

            def get_treatment_for_disease(d: str) -> str:
                return get_treatment(str(d))

            if fam_tr and fam_tr.last_disease:
                response_xml = _twiml(get_treatment_for_disease(fam_tr.last_disease))
                return await _finalize_and_return(provider_message_id, response_xml)
            response_xml = _twiml(
                "🌿 Please send an image first so I can detect the disease and suggest treatment."
            )
            return await _finalize_and_return(provider_message_id, response_xml)

        has_media = num_media > 0 and bool(media_url)
        is_price_query = "price" in message_lower
        is_mandi_query = "mandi" in message_lower

        if not any([has_media, is_price_query, is_mandi_query]):
            db_i = AsyncSessionLocal()
            try:
                hist_i = await get_recent_messages(db_i, phone, limit=10)
                ctx_i = await _farmer_llm_context(phone)
            finally:
                await db_i.close()
            try:
                reply_i = await process_message(
                    farmer_id=phone,
                    message=body or "Hello",
                    language=farmer_language or "Hindi",
                    history=hist_i,
                    disease_result=None,
                    context=ctx_i,
                )
            except Exception as llm_e:
                print("LLM fallback failed:", llm_e)
                reply_i = (
                    "⚠️ I'm having trouble answering that. Please try again."
                )
            db_i2 = AsyncSessionLocal()
            try:
                await append_message_pair(db_i2, phone, body or "Hello", reply_i)
            finally:
                await db_i2.close()
            return await _finalize_and_return(provider_message_id, _twiml(reply_i))

        image_path = None
        disease_result = None
        reply_override = None
        disease_persisted = False

        if has_media:
            img_check = check_image(content_type)
            if not img_check.allowed:
                response_xml = _twiml(img_check.reply)
                return await _finalize_and_return(provider_message_id, response_xml)

            try:
                image_path = await _download_image(media_url, content_type)
            except Exception as e:
                print(f"[WhatsApp] image download failed: {e}")
                response_xml = _twiml("Image download failed. Please resend the image.")
                return await _finalize_and_return(provider_message_id, response_xml)

            try:
                if image_path and os.path.exists(CLASSIFIER_PATH):
                    disease_result = diagnose_image(
                        image_path=image_path,
                        classifier_path=CLASSIFIER_PATH,
                        detector_path=DETECTOR_PATH
                        if os.path.exists(DETECTOR_PATH)
                        else None,
                    )
            except Exception as e:
                print("Disease error:", e)
                disease_result = None

            if not disease_result:
                reply_override = None
            elif disease_result.get("error"):
                pass
            else:
                raw_l = (disease_result.get("raw_name") or "").lower()
                if "healthy" in raw_l:
                    reply_override = NO_DISEASE_REPLY
                else:
                    try:
                        conf_i = int(
                            float(
                                str(disease_result.get("confidence", 0)).replace(
                                    "%", ""
                                )
                            )
                        )
                    except (TypeError, ValueError):
                        conf_i = 30
                    if conf_i < 30:
                        reply_override = LOW_CONFIDENCE_REPLY

            if (
                disease_result
                and not disease_result.get("error")
                and reply_override is None
            ):
                raw_l2 = (disease_result.get("raw_name") or "").lower()
                if "healthy" not in raw_l2 and parse_confidence(
                    disease_result.get("confidence")
                ) >= 30:
                    db_pe = AsyncSessionLocal()
                    try:
                        await add_disease(db_pe, phone, disease_result)
                        fam_ad, _ = await _get_or_create_farmer(db_pe, phone)
                        if fam_ad and disease_result.get("disease"):
                            fam_ad.last_disease = disease_result.get("disease")
                            await db_pe.commit()
                        disease_persisted = True
                    finally:
                        await db_pe.close()

                    from backend.scheduler import schedule_followup

                    confidence = parse_confidence(disease_result.get("confidence"))
                    schedule_followup(
                        phone=phone,
                        farmer_name="Farmer",
                        disease_name=disease_result.get("disease") or "unknown",
                        bbox_pct=confidence,
                    )

                    try:
                        from backend.outbreak.service import handle_new_detection

                        db_ob = AsyncSessionLocal()
                        try:
                            farmer_ob, _ = await _get_or_create_farmer(db_ob, phone)
                            crop_val = (
                                farmer_ob.crops[0]
                                if farmer_ob and farmer_ob.crops
                                else None
                            )
                            detection_data = {
                                "phone": phone,
                                "disease_name": disease_result.get("disease"),
                                "crop_type": crop_val,
                                "severity": parse_confidence(
                                    disease_result.get("confidence")
                                ),
                                "lat": getattr(farmer_ob, "lat", None)
                                if farmer_ob
                                else None,
                                "lng": getattr(farmer_ob, "lng", None)
                                if farmer_ob
                                else None,
                                "spread": True,
                            }

                            result = await db_ob.execute(
                                text(
                                    """
                                    INSERT INTO detections
                                    (phone, disease_name, crop_type, severity, lat, lng, spread, processed)
                                    VALUES (:phone, :disease_name, :crop_type, :severity, :lat, :lng, :spread, false)
                                    RETURNING id
                                    """
                                ),
                                detection_data,
                            )
                            row = result.fetchone()
                            if row:
                                detection_data["id"] = row[0]
                            await db_ob.commit()
                        finally:
                            await db_ob.close()

                        await handle_new_detection(db=None, detection=detection_data)
                    except Exception as e:
                        print("Outbreak integration error:", e)

        if not has_media and (is_mandi_query or is_price_query):
            text_location = extract_location(body)
            db = AsyncSessionLocal()
            try:
                farmer_m, _ = await _get_or_create_farmer(db, phone)
                f_lat = getattr(farmer_m, "lat", None) if farmer_m else None
                f_lng = getattr(farmer_m, "lng", None) if farmer_m else None
                saved_crops = list(farmer_m.crops or []) if farmer_m else []
                saved_crop = saved_crops[0] if saved_crops else None
                history_m = await get_recent_messages(db, phone, limit=10)
            finally:
                await db.close()

            farmer_has_gps = f_lat is not None and f_lng is not None
            commodity = extract_crop_name(body)

            if is_mandi_query and not is_price_query:
                mandi_crop = commodity or saved_crop or "onion"
                extracted = await extract_farmer_data(body)
                loc_up = extracted.get("location") if not text_location else None
                db = AsyncSessionLocal()
                try:
                    await upsert_farmer_profile(
                        db,
                        phone,
                        location=loc_up,
                        crop=extracted.get("crop"),
                    )
                    if text_location:
                        results = await find_best_mandi_for_commodity(
                            commodity=mandi_crop,
                            location_name=text_location,
                            radius_km=500,
                            top_n=5,
                            db=db,
                        )
                    else:
                        if not farmer_has_gps:
                            response_xml = _twiml(LOCATION_PROMPT)
                            return await _finalize_and_return(
                                provider_message_id, response_xml
                            )
                        lat_use, lng_use = float(f_lat), float(f_lng)
                        results = await find_best_mandi_for_commodity(
                            farmer_lat=lat_use,
                            farmer_lng=lng_use,
                            commodity=mandi_crop,
                            radius_km=500,
                            top_n=5,
                            db=db,
                        )
                finally:
                    await db.close()

                if results:
                    lines = "\n".join(f"• {m['market']}" for m in results[:3])
                    reply = (
                        "📍 Nearby mandis in your area:\n"
                        f"{lines}\n\n"
                        f"{MANDI_ONLY_FOOTER}"
                    )
                else:
                    ctx_md = await _farmer_llm_context(phone)
                    try:
                        reply = await process_message(
                            farmer_id=phone,
                            message=body or "Hello",
                            disease_result=None,
                            language=farmer_language,
                            history=history_m,
                            context=ctx_md,
                        )
                    except Exception as llm_e:
                        print("LLM fallback failed:", llm_e)
                        reply = (
                            "⚠️ I'm having trouble answering that. Please try again."
                        )

                db = AsyncSessionLocal()
                try:
                    await append_message_pair(db, phone, body or "Hello", reply)
                finally:
                    await db.close()

                response_xml = _twiml(reply)
                return await _finalize_and_return(provider_message_id, response_xml)

            if is_price_query:
                if commodity:
                    crop = commodity
                elif saved_crop:
                    crop = saved_crop
                else:
                    response_xml = _twiml(PRICE_ASK_CROP)
                    return await _finalize_and_return(provider_message_id, response_xml)

                extracted = await extract_farmer_data(body)
                loc_up = extracted.get("location") if not text_location else None
                db = AsyncSessionLocal()
                try:
                    await upsert_farmer_profile(
                        db,
                        phone,
                        location=loc_up,
                        crop=extracted.get("crop"),
                    )
                    if text_location:
                        results = await find_best_mandi_for_commodity(
                            commodity=crop,
                            location_name=text_location,
                            radius_km=500,
                            top_n=5,
                            db=db,
                        )
                    else:
                        if not farmer_has_gps:
                            response_xml = _twiml(LOCATION_PROMPT)
                            return await _finalize_and_return(
                                provider_message_id, response_xml
                            )
                        lat_use, lng_use = float(f_lat), float(f_lng)
                        results = await find_best_mandi_for_commodity(
                            farmer_lat=lat_use,
                            farmer_lng=lng_use,
                            commodity=crop,
                            radius_km=500,
                            top_n=5,
                            db=db,
                        )
                finally:
                    await db.close()

                if not results:
                    ctx_p = await _farmer_llm_context(phone)
                    try:
                        reply = await process_message(
                            farmer_id=phone,
                            message=body or "Hello",
                            disease_result=None,
                            language=farmer_language,
                            history=history_m,
                            context=ctx_p,
                        )
                    except Exception as llm_e:
                        print("LLM fallback failed:", llm_e)
                        reply = (
                            "⚠️ I'm having trouble answering that. Please try again."
                        )
                else:
                    reply = _format_smart_mandi_text(
                        results, crop, farmer_language
                    )

                db = AsyncSessionLocal()
                try:
                    await append_message_pair(db, phone, body or "Hello", reply)
                finally:
                    await db.close()

                response_xml = _twiml(reply)
                return await _finalize_and_return(provider_message_id, response_xml)

        extracted = await extract_farmer_data(body)
        text_loc_general = extract_location(body)

        db = AsyncSessionLocal()
        try:
            await upsert_farmer_profile(
                db,
                phone,
                location=(
                    extracted.get("location") if not text_loc_general else None
                ),
                crop=extracted.get("crop"),
            )
            _record_disease = (
                disease_result
                and not disease_result.get("error")
                and reply_override is None
                and not disease_persisted
                and (
                    not has_media
                    or (
                        "healthy"
                        not in (disease_result.get("raw_name") or "").lower()
                        and parse_confidence(disease_result.get("confidence")) >= 30
                    )
                )
            )
            if _record_disease:
                await add_disease(db, phone, disease_result)

            history = await get_recent_messages(db, phone, limit=10)
        finally:
            await db.close()

        try:
            if reply_override is not None:
                reply = reply_override
            elif (
                has_media
                and disease_result
                and not disease_result.get("error")
                and "healthy" not in (disease_result.get("raw_name") or "").lower()
                and parse_confidence(disease_result.get("confidence")) >= 30
            ):
                reply = format_disease_response(disease_result)
            else:
                ctx_lm = await _farmer_llm_context(phone)
                reply = await process_message(
                    farmer_id=phone,
                    message=body or "Hello",
                    language=farmer_language,
                    history=history,
                    disease_result=disease_result,
                    context=ctx_lm,
                )
        except Exception as e:
            print("LLM fallback failed:", e)
            reply = "⚠️ I'm having trouble answering that. Please try again."

        db = AsyncSessionLocal()
        try:
            await append_message_pair(db, phone, body or "Hello", reply)
        finally:
            await db.close()

        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass

        response_xml = _twiml(reply)
        return await _finalize_and_return(provider_message_id, response_xml)

    except Exception as e:
        print(f"[WhatsApp] handle_incoming_message error: {e}")
        db_fb = AsyncSessionLocal()
        hist_fb: list = []
        try:
            hist_fb = await get_recent_messages(db_fb, phone, limit=10)
        except Exception:
            pass
        finally:
            await db_fb.close()
        try:
            ctx_fb = await _farmer_llm_context(phone)
            reply = await process_message(
                farmer_id=phone,
                message=body or "Hello",
                disease_result=None,
                language=farmer_language or "Hindi",
                history=hist_fb,
                context=ctx_fb,
            )
            return await _finalize_and_return(provider_message_id, _twiml(reply))
        except Exception:
            return await _fail_and_return(
                provider_message_id,
                str(e),
                "Sorry, something went wrong. Please try again. 🌾",
            )


async def handle_location_for_mandi(
    phone: str,
    lat: float,
    lng: float,
    commodity: str | None,
    language: str = "Hindi",
) -> str:
    lang = (language or "Hindi").strip().lower()

    if not commodity:
        db = AsyncSessionLocal()
        try:
            results = await find_best_mandi_for_commodity(
                farmer_lat=lat,
                farmer_lng=lng,
                commodity=commodity,
                radius_km=300,
                top_n=5,
                db=db,
            )
        finally:
            await db.close()

        if not results:
            if lang == "english":
                return "No nearby mandi found.\n\nNeed any other help? 🌾"
            if lang == "kannada":
                return "ನಿಮ್ಮ ಹತ್ತಿರ ಯಾವುದೇ ಮಂಡಿ ಸಿಗಲಿಲ್ಲ.\n\nಇನ್ನೇನಾದರೂ ಸಹಾಯ ಬೇಕೇ? 🌾"
            return "Aapke paas koi mandi nahi mili.\n\nKoi aur madad chahiye? 🌾"

        if lang == "english":
            reply = "*Nearest mandis to you:*\n\n"
            for i, m in enumerate(results, 1):
                dist = m.get("distance_km", m.get("distance", "?"))
                reply += f"{i}. *{m['market']}* - {dist} km\n"
                if m.get("district"):
                    reply += f"   {m['district']}, {m['state']}\n"
            reply += "\nNeed any other help? 🌾"
            return reply

        if lang == "kannada":
            reply = "*ನಿಮಗೆ ಹತ್ತಿರದ ಮಂಡಿಗಳು:*\n\n"
            for i, m in enumerate(results, 1):
                dist = m.get("distance_km", m.get("distance", "?"))
                reply += f"{i}. *{m['market']}* - {dist} km\n"
                if m.get("district"):
                    reply += f"   {m['district']}, {m['state']}\n"
            reply += "\nಇನ್ನೇನಾದರೂ ಸಹಾಯ ಬೇಕೇ? 🌾"
            return reply

        reply = "*Aapke sabse paas ke mandis:*\n\n"
        for i, m in enumerate(results, 1):
            dist = m.get("distance_km", m.get("distance", "?"))
            reply += f"{i}. *{m['market']}* - {dist} km\n"
            if m.get("district"):
                reply += f"   {m['district']}, {m['state']}\n"
        reply += "\nKoi aur madad chahiye? 🌾"
        return reply

    db = AsyncSessionLocal()
    try:
        results = await find_best_mandi_for_commodity(
            farmer_lat=lat,
            farmer_lng=lng,
            commodity=commodity,
            radius_km=500,
            top_n=3,
            db=db,
        )
    finally:
        await db.close()

    if not results:
        if lang == "english":
            return (
                f"No mandi found within 500 km for *{commodity.title()}*.\n"
                f"Run: POST /market/fetch\n\n"
                f"Need any other help? 🌾"
            )
        if lang == "kannada":
            return (
                f"*{commodity.title()}*ಗಾಗಿ 500 ಕಿಮೀ ಒಳಗೆ ಯಾವುದೇ ಮಂಡಿ ಸಿಗಲಿಲ್ಲ.\n"
                f"ಮೊದಲು ಇದು ರನ್ ಮಾಡಿ: POST /market/fetch\n\n"
                f"ಇನ್ನೇನಾದರೂ ಸಹಾಯ ಬೇಕೇ? 🌾"
            )
        return (
            f"*{commodity.title()}* ke liye 500km mein koi mandi nahi mili.\n"
            f"Pehle yeh run karein: POST /market/fetch\n\n"
            f"Koi aur madad chahiye? 🌾"
        )

    best = results[0]

    if lang == "english":
        reply = (
            f"*Best mandi for {commodity.title()}:*\n\n"
            f"*{best['market']}*"
            + (
                f", {best['district']}, {best['state']}\n"
                if best.get("district")
                else "\n"
            )
            + f"Modal Rate : Rs.{best['modal_price']}/quintal\n"
            + f"Distance   : {best.get('distance_km', best.get('distance', '?'))} km\n"
        )
        if best.get("transport_cost") is not None:
            reply += f"Transport  : Rs.{best['transport_cost']}\n"
        if best.get("net_price") is not None:
            reply += f"*Net Price : Rs.{best['net_price']}/quintal* ✅\n"
        if len(results) > 1:
            reply += "\n*Other options:*\n"
            for m in results[1:]:
                dist = m.get("distance_km", m.get("distance", "?"))
                np = m.get("net_price", m.get("modal_price"))
                reply += f"  • {m['market']} - Rs.{np}/q ({dist}km)\n"
        reply += "\nNeed any other help? 🌾"
        return reply

    if lang == "kannada":
        reply = (
            f"*{commodity.title()}ಗೆ ಅತ್ಯುತ್ತಮ ಮಂಡಿ:*\n\n"
            f"*{best['market']}*"
            + (
                f", {best['district']}, {best['state']}\n"
                if best.get("district")
                else "\n"
            )
            + f"Modal Rate : Rs.{best['modal_price']}/quintal\n"
            + f"Distance   : {best.get('distance_km', best.get('distance', '?'))} km\n"
        )
        if best.get("transport_cost") is not None:
            reply += f"Transport  : Rs.{best['transport_cost']}\n"
        if best.get("net_price") is not None:
            reply += f"*Net Price : Rs.{best['net_price']}/quintal* ✅\n"
        if len(results) > 1:
            reply += "\n*ಇತರೆ ಆಯ್ಕೆಗಳು:*\n"
            for m in results[1:]:
                dist = m.get("distance_km", m.get("distance", "?"))
                np = m.get("net_price", m.get("modal_price"))
                reply += f"  • {m['market']} - Rs.{np}/q ({dist}km)\n"
        reply += "\nಇನ್ನೇನಾದರೂ ಸಹಾಯ ಬೇಕೇ? 🌾"
        return reply

    reply = (
        f"*{commodity.title()} ke liye sabse acchi mandi:*\n\n"
        f"*{best['market']}*"
        + (f", {best['district']}, {best['state']}\n" if best.get("district") else "\n")
        + f"Modal Rate : Rs.{best['modal_price']}/quintal\n"
        + f"Doori      : {best.get('distance_km', best.get('distance', '?'))} km\n"
    )
    if best.get("transport_cost") is not None:
        reply += f"Transport  : Rs.{best['transport_cost']}\n"
    if best.get("net_price") is not None:
        reply += f"*Net Price : Rs.{best['net_price']}/quintal* ✅\n"
    if len(results) > 1:
        reply += "\n*Doosre options:*\n"
        for m in results[1:]:
            dist = m.get("distance_km", m.get("distance", "?"))
            np = m.get("net_price", m.get("modal_price"))
            reply += f"  • {m['market']} - Rs.{np}/q ({dist}km)\n"

    reply += "\nKoi aur madad chahiye? 🌾"
    return reply


async def send_proactive_message(phone: str, message: str):
    phone_clean = (phone or "").replace("whatsapp:", "").strip()
    if not phone_clean:
        print("❌ WhatsApp send skipped: missing phone")
        return
    if not ACCOUNT_SID or not AUTH_TOKEN or not FROM_NUMBER:
        print("❌ WhatsApp send skipped: missing Twilio env")
        print(f"📲 [FALLBACK MESSAGE to {phone_clean}]")
        print(message)
        return

    to_addr = (
        phone_clean
        if phone_clean.startswith("whatsapp:")
        else f"whatsapp:{phone_clean}"
    )

    def _send():
        return twilio_client.messages.create(
            body=message,
            from_=FROM_NUMBER,
            to=to_addr,
        )

    try:
        msg = await asyncio.to_thread(_send)
        print("✅ WhatsApp sent:", msg.sid)
    except Exception as e:
        print("❌ WhatsApp failed, switching to terminal fallback", e)
        print(f"📲 [FALLBACK MESSAGE to {phone_clean}]")
        print(message)


async def _download_image(media_url: str, content_type: str) -> str:
    ext_map = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    ext = ext_map.get(content_type, ".jpg")
    filepath = os.path.join(TEMP_DIR, f"kisan_{uuid.uuid4().hex}{ext}")

    async with httpx.AsyncClient(auth=HTTPBasicAuth(ACCOUNT_SID, AUTH_TOKEN)) as client:
        response = await client.get(media_url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(response.content)

    return filepath
