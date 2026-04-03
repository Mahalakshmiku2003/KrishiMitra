import os
import uuid
import httpx
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from backend.agent.agent import process_message
from backend.agent.diagnose import diagnose_image
from backend.agent.guardrails import check_message, check_image
from backend.services.location_state import clear_pending_location_action
from backend.services.db import SessionLocal
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

    # idempotency guard
    db = AsyncSessionLocal()
    try:
        inbound_state = await reserve_inbound_message(
            db,
            provider_message_id=provider_message_id,
            phone=phone,
            body=body,
        )
    finally:
        await db.close()

    if inbound_state["state"] == "duplicate_done":
        return inbound_state["response_xml"]

    if inbound_state["state"] == "duplicate_inflight":
        return _twiml(
            "Your request is already being processed. Please wait a moment. 🌾"
        )

    try:
        db = AsyncSessionLocal()
        try:
            farmer, _ = await _get_or_create_farmer(db, phone)
            farmer_language = farmer.language if farmer and farmer.language else None
        finally:
            await db.close()

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
                response_xml = _twiml(LANGUAGE_MENU)
                return await _finalize_and_return(provider_message_id, response_xml)

            db = AsyncSessionLocal()
            try:
                await set_farmer_language(db, phone, selected)
            finally:
                await db.close()

            response_xml = _twiml(LANGUAGE_CONFIRM[selected])
            return await _finalize_and_return(provider_message_id, response_xml)

        msg_check = check_message(body)
        if not msg_check.allowed:
            response_xml = _twiml(msg_check.reply)
            return await _finalize_and_return(provider_message_id, response_xml)

        image_path = None
        if num_media > 0 and media_url:
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

        disease_result = None
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
            print(f"[WhatsApp] diagnosis failed: {e}")

        extracted = await extract_farmer_data(body)

        db = AsyncSessionLocal()
        try:
            await upsert_farmer_profile(
                db,
                phone,
                location=extracted.get("location"),
                crop=extracted.get("crop"),
            )
            if disease_result and not disease_result.get("error"):
                await add_disease(db, phone, disease_result)

            history = await get_recent_messages(db, phone, limit=10)
        finally:
            await db.close()
        message = form_data.get("Body", "")
        if "follow up" in message.lower() or "followup" in message.lower():
            from backend.scheduler import schedule_followup
            from twilio.twiml.messaging_response import MessagingResponse

            phone = form_data.get("From", "").replace("whatsapp:", "").strip().lower()

            schedule_followup(
                phone=phone,
                farmer_name="Farmer",
                disease_name="recent issue",
                bbox_pct=30,
            )

            twiml = MessagingResponse()
            twiml.message("✅ Follow-up scheduled. I will check back soon.")
            return await _finalize_and_return(provider_message_id, str(twiml))
        reply = await process_message(
            farmer_id=phone,
            message=body or "Hello",
            disease_result=disease_result,
            language=farmer_language,
            history=history,
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
            nearest = await find_best_mandi_for_commodity(
                farmer_lat=lat,
                farmer_lng=lng,
                commodity=commodity,
                radius_km=300,
                top_n=5,
                db=db,
            )
        finally:
            await db.close()

        if not nearest:
            if lang == "english":
                return "No nearby mandi found.\n\nNeed any other help? 🌾"
            if lang == "kannada":
                return "ನಿಮ್ಮ ಹತ್ತಿರ ಯಾವುದೇ ಮಂಡಿ ಸಿಗಲಿಲ್ಲ.\n\nಇನ್ನೇನಾದರೂ ಸಹಾಯ ಬೇಕೇ? 🌾"
            return "Aapke paas koi mandi nahi mili.\n\nKoi aur madad chahiye? 🌾"

        if lang == "english":
            reply = "*Nearest mandis to you:*\n\n"
            for i, m in enumerate(nearest, 1):
                reply += f"{i}. *{m['market']}* — {m['distance_km']} km\n"
                if m.get("district"):
                    reply += f"   {m['district']}, {m['state']}\n"
            reply += "\nNeed any other help? 🌾"
            return reply

        if lang == "kannada":
            reply = "*ನಿಮಗೆ ಹತ್ತಿರದ ಮಂಡಿಗಳು:*\n\n"
            for i, m in enumerate(nearest, 1):
                reply += f"{i}. *{m['market']}* — {m['distance_km']} km\n"
                if m.get("district"):
                    reply += f"   {m['district']}, {m['state']}\n"
            reply += "\nಇನ್ನೇನಾದರೂ ಸಹಾಯ ಬೇಕೇ? 🌾"
            return reply

        reply = "*Aapke sabse paas ke mandis:*\n\n"
        for i, m in enumerate(nearest, 1):
            reply += f"{i}. *{m['market']}* — {m['distance_km']} km\n"
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
            f"*{best['market']}*, {best['district']}, {best['state']}\n"
            f"Modal Rate : Rs.{best['modal_price']}/quintal\n"
            f"Distance   : {best['distance_km']} km\n"
            f"Transport  : Rs.{best['transport_cost']}\n"
            f"*Net Price : Rs.{best['net_price']}/quintal* ✅\n"
        )
        if len(results) > 1:
            reply += "\n*Other options:*\n"
            for m in results[1:]:
                reply += f"  • {m['market']} — Rs.{m['net_price']}/q ({m['distance_km']}km)\n"
        reply += "\nNeed any other help? 🌾"
        return reply

    if lang == "kannada":
        reply = (
            f"*{commodity.title()}ಗೆ ಅತ್ಯುತ್ತಮ ಮಂಡಿ:*\n\n"
            f"*{best['market']}*, {best['district']}, {best['state']}\n"
            f"Modal Rate : Rs.{best['modal_price']}/quintal\n"
            f"Distance   : {best['distance_km']} km\n"
            f"Transport  : Rs.{best['transport_cost']}\n"
            f"*Net Price : Rs.{best['net_price']}/quintal* ✅\n"
        )
        if len(results) > 1:
            reply += "\n*ಇತರೆ ಆಯ್ಕೆಗಳು:*\n"
            for m in results[1:]:
                reply += f"  • {m['market']} — Rs.{m['net_price']}/q ({m['distance_km']}km)\n"
        reply += "\nಇನ್ನೇನಾದರೂ ಸಹಾಯ ಬೇಕೇ? 🌾"
        return reply

    reply = (
        f"*{commodity.title()} ke liye sabse acchi mandi:*\n\n"
        f"*{best['market']}*, {best['district']}, {best['state']}\n"
        f"Modal Rate : Rs.{best['modal_price']}/quintal\n"
        f"Doori      : {best['distance_km']} km\n"
        f"Transport  : Rs.{best['transport_cost']}\n"
        f"*Net Price : Rs.{best['net_price']}/quintal* ✅\n"
    )
    if len(results) > 1:
        reply += "\n*Doosre options:*\n"
        for m in results[1:]:
            reply += (
                f"  • {m['market']} — Rs.{m['net_price']}/q ({m['distance_km']}km)\n"
            )

    reply += "\nKoi aur madad chahiye? 🌾"
    return reply


async def send_proactive_message(phone: str, message: str):
    try:
        twilio_client.messages.create(
            from_=FROM_NUMBER,
            to=f"whatsapp:{phone}",
            body=(message or "")[:1599],
        )
        print(f"[WhatsApp] proactive message sent to {phone}")
    except Exception as e:
        print(f"[WhatsApp] send failed to {phone}: {e}")


async def _download_image(media_url: str, content_type: str) -> str:
    ext_map = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    ext = ext_map.get(content_type, ".jpg")
    filepath = os.path.join(TEMP_DIR, f"kisan_{uuid.uuid4().hex}{ext}")

    auth = httpx.BasicAuth(ACCOUNT_SID, AUTH_TOKEN)
    async with httpx.AsyncClient(auth=auth) as client:
        response = await client.get(media_url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(response.content)

    return filepath
