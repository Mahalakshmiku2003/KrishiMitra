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
}


def parse_confidence(val):
    try:
        return int(float(str(val).replace("%", "")))
    except (TypeError, ValueError):
        return 30


def extract_location(text: str) -> str | None:
    if not (text or "").strip():
        return None
    lower = text.lower()
    cities = [
        "bangalore",
        "bengaluru",
        "kolar",
        "mysore",
        "mysuru",
        "pune",
        "mumbai",
        "delhi",
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
    ]
    for c in cities:
        if c in lower:
            return c
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

        has_media = num_media > 0 and bool(media_url)
        mandi_intent = "price" in message_lower or "mandi" in message_lower

        image_path = None
        disease_result = None
        reply_override = None

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
                reply_override = NO_DISEASE_REPLY
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

        if not has_media and mandi_intent:
            text_city = extract_location(body)
            db = AsyncSessionLocal()
            try:
                farmer_m, _ = await _get_or_create_farmer(db, phone)
                f_lat = getattr(farmer_m, "lat", None) if farmer_m else None
                f_lng = getattr(farmer_m, "lng", None) if farmer_m else None
                saved_crops = list(farmer_m.crops or []) if farmer_m else []
                history_m = await get_recent_messages(db, phone, limit=10)
            finally:
                await db.close()

            farmer_has_gps = f_lat is not None and f_lng is not None

            commodity = extract_crop_name(body)
            if not commodity and saved_crops:
                commodity = saved_crops[0]
            if not commodity:
                response_xml = _twiml(MANDI_ASK_CROP)
                return await _finalize_and_return(provider_message_id, response_xml)

            if not farmer_has_gps and not text_city:
                response_xml = _twiml(LOCATION_PROMPT)
                return await _finalize_and_return(provider_message_id, response_xml)

            lat_use: float | None = None
            lng_use: float | None = None
            if farmer_has_gps:
                lat_use = float(f_lat)
                lng_use = float(f_lng)
            elif text_city:
                coords = CITY_COORDS.get(text_city.lower())
                if coords:
                    lat_use, lng_use = float(coords[0]), float(coords[1])

            if lat_use is None or lng_use is None:
                response_xml = _twiml(LOCATION_PROMPT)
                return await _finalize_and_return(provider_message_id, response_xml)

            extracted = await extract_farmer_data(body)
            db = AsyncSessionLocal()
            try:
                await upsert_farmer_profile(
                    db,
                    phone,
                    location=extracted.get("location"),
                    crop=extracted.get("crop"),
                )
                if commodity:
                    results = await find_best_mandi_for_commodity(
                        farmer_lat=lat_use,
                        farmer_lng=lng_use,
                        commodity=commodity,
                        radius_km=500,
                        top_n=5,
                        db=db,
                    )
                else:
                    results = []
            finally:
                await db.close()

            if not results:
                reply = await process_message(
                    farmer_id=phone,
                    message=body or "Hello",
                    disease_result=None,
                    language=farmer_language,
                    history=history_m,
                )
            else:
                reply = _format_smart_mandi_text(
                    results, commodity or "crop", farmer_language
                )

            db = AsyncSessionLocal()
            try:
                await append_message_pair(db, phone, body or "Hello", reply)
            finally:
                await db.close()

            response_xml = _twiml(reply)
            return await _finalize_and_return(provider_message_id, response_xml)

        extracted = await extract_farmer_data(body)

        db = AsyncSessionLocal()
        try:
            await upsert_farmer_profile(
                db,
                phone,
                location=extracted.get("location"),
                crop=extracted.get("crop"),
            )
            _record_disease = (
                disease_result
                and not disease_result.get("error")
                and reply_override is None
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
            reply = await process_message(
                farmer_id=phone,
                message=body or "Hello",
                language=farmer_language,
                history=history,
                disease_result=disease_result,
            )

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
            reply = await process_message(
                farmer_id=phone,
                message=body or "Hello",
                disease_result=None,
                language=farmer_language or "Hindi",
                history=hist_fb,
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
    print("\n📲 [SIMULATED WHATSAPP MESSAGE]")
    print(f"To: {phone}")
    print(message)
    print("=" * 50)


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
