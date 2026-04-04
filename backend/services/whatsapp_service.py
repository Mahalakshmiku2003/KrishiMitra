"""
services/whatsapp_service.py
"""

import asyncio
import os
import uuid
import tempfile
from pathlib import Path
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

from agent.agent import process_message
from agent.diagnose import diagnose_image
from agent.guardrails import check_message, check_image
from services.location_state import _pending_location
from services.db import SessionLocal

from farmer_store import (
    get_farmer_location,
    save_farmer_location,
    record_detection_if_outbreak,
    save_farmer_diagnosis,
)
from services.language_onboarding import maybe_handle_language_onboarding
from services.name_onboarding import maybe_handle_name_onboarding
from services.market_service import find_nearest_from_json, find_best_mandi_for_commodity

load_dotenv()

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
FROM_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

twilio_client = Client(ACCOUNT_SID, AUTH_TOKEN)
TEMP_DIR  = tempfile.gettempdir()

AGENT_DIR = Path(__file__).resolve().parent.parent / "agent"
_MODEL_DIR = AGENT_DIR / "model"
if not (_MODEL_DIR / "classifier.onnx").exists():
    _MODEL_DIR = AGENT_DIR / "models"
CLASSIFIER_PATH = str(_MODEL_DIR / "classifier.onnx")
DETECTOR_PATH   = str(_MODEL_DIR / "detector.onnx")


async def handle_incoming_message(form_data: dict) -> str:
    """Single handler — location check first, then normal agent flow."""
    print(f"[DEBUG] Full form_data: {form_data}")

    phone     = form_data.get("From", "").replace("whatsapp:", "").strip()
    body      = form_data.get("Body", "").strip()
    num_media = int(form_data.get("NumMedia", 0))
    media_url = form_data.get("MediaUrl0")
    content_type = form_data.get("MediaContentType0")
    latitude  = form_data.get("Latitude")
    longitude = form_data.get("Longitude")

    print(f"[DEBUG] lat={latitude}, lng={longitude}, pending={phone in _pending_location}")

    # ── 1. Location message — handle before everything else ──────────────────
    if latitude and longitude:
        lat = float(latitude)
        lng = float(longitude)

        # Save permanently — only matters first time, safe to overwrite
        save_farmer_location(phone, lat, lng)
        context   = _pending_location.pop(phone, None)
        commodity = context.get("commodity") if context else None  # None = Flow B
        state_filter = context.get("state_filter") if context else None
        reply = await handle_location_for_mandi(
            phone=phone,
            lat=float(latitude),
            lng=float(longitude),
            commodity=commodity,
            state_filter=state_filter,
        )
        twiml = MessagingResponse()
        twiml.message(reply)
        return str(twiml)

    # ── 2. Image message ─────────────────────────────────────────────────────
    image_path = None
    if num_media > 0 and media_url:
        img_check = check_image(content_type)
        if not img_check.allowed:
            twiml = MessagingResponse()
            twiml.message(img_check.reply)
            return str(twiml)
        try:
            image_path = await _download_image(media_url, content_type)
        except Exception as e:
            print(f"[WhatsApp] Image download failed: {e}")

    # ── 3. Guardrail check ───────────────────────────────────────────────────
    msg_check = check_message(body)
    if not msg_check.allowed:
        twiml = MessagingResponse()
        twiml.message(msg_check.reply)
        return str(twiml)

    # ── 3b. Language preference (first contact: hi/hello or 1/2/3) ───────────
    if num_media == 0:
        lang_reply = maybe_handle_language_onboarding(phone, body)
        if lang_reply is not None:
            twiml = MessagingResponse()
            twiml.message(lang_reply)
            return str(twiml)

    # ── 3c. Name (after language) ─────────────────────────────────────────────
    if num_media == 0:
        name_reply = maybe_handle_name_onboarding(phone, body)
        if name_reply is not None:
            twiml = MessagingResponse()
            twiml.message(name_reply)
            return str(twiml)

    # ── 4. Normal agent flow ─────────────────────────────────────────────────
    disease_result = None
    if image_path and os.path.exists(CLASSIFIER_PATH):
        disease_result = diagnose_image(
            image_path=image_path,
            classifier_path=CLASSIFIER_PATH,
            detector_path=DETECTOR_PATH if os.path.exists(DETECTOR_PATH) else None,
        )
    elif image_path:
        print(f"[WhatsApp] Missing classifier at {CLASSIFIER_PATH}")

    if disease_result:
        save_farmer_diagnosis(phone, disease_result, body)
        record_detection_if_outbreak(phone, disease_result)

    reply = await process_message(
        farmer_id=phone,
        message=body or "Hello",
        disease_result=disease_result,
    )

    if image_path and os.path.exists(image_path):
        os.remove(image_path)

    twiml = MessagingResponse()
    twiml.message(reply)
    twiml_str = str(twiml)
    print(f"[DEBUG] Sending TwiML: {twiml_str}")
    return twiml_str


# services/whatsapp_service.py — replace handle_location_for_mandi entirely



async def handle_location_for_mandi(
    phone: str,
    lat: float,
    lng: float,
    commodity: str | None,
    state_filter: str | None = None,
) -> str:

    # ── Flow B: no commodity — nearest mandis from JSON ──────────────────────
    if not commodity:
        nearest = find_nearest_from_json(lat, lng, top_n=5, state=state_filter)
        if not nearest:
            hint = f" ({state_filter})" if state_filter else ""
            return (
                f"Aapke paas{hint} koi mandi nahi mili (data mein).\n\n"
                f"Koi aur madad chahiye? 🌾"
            )

        if state_filter:
            reply = f"*{state_filter}* ke mandi (aapki location se doori):\n\n"
        else:
            reply = "*Aapke sabse paas ke mandis:*\n\n"
        for i, m in enumerate(nearest, 1):
            reply += f"{i}. *{m['market']}* — {m['distance_km']} km\n"
            if m.get("district"):
                reply += f"   {m['district']}, {m['state']}\n"
        reply += "\nKoi aur madad chahiye? 🌾"
        return reply

    # ── Flow A: commodity given — best price from DB ──────────────────────────
    db = SessionLocal()
    try:
        results = find_best_mandi_for_commodity(
            farmer_lat=lat,
            farmer_lng=lng,
            commodity=commodity,
            radius_km=500,
            top_n=3,
            db=db,
            state=state_filter,
        )
    finally:
        db.close()

    if not results:
        st = f" *{state_filter}* mein" if state_filter else ""
        return (
            f"*{commodity.title()}* ke liye{st} 500km mein koi mandi nahi mili "
            f"(database / coordinates).\n"
            f"Doosre state ke liye message mein state ka naam likhein, phir location bhejein.\n\n"
            f"Koi aur madad chahiye? 🌾"
        )

    best = results[0]
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
            reply += f"  • {m['market']} — Rs.{m['net_price']}/q ({m['distance_km']}km)\n"

    reply += "\nKoi aur madad chahiye? 🌾"
    return reply


async def send_proactive_message(phone: str, message: str):
    try:
        twilio_client.messages.create(
            from_=FROM_NUMBER,
            to=f"whatsapp:{phone}",
            body=message,
        )
        print(f"[WhatsApp] Proactive message sent to {phone}")
    except Exception as e:
        print(f"[WhatsApp] Failed to send to {phone}: {e}")


async def _download_image(media_url: str, content_type: str) -> str:
    from services.twilio_media_download import download_twilio_media_sync

    ext_map = {
        "image/jpeg": ".jpg",
        "image/jpg":  ".jpg",
        "image/png":  ".png",
        "image/webp": ".webp",
    }
    ext = ext_map.get(content_type, ".jpg")
    filepath = os.path.join(TEMP_DIR, f"kisan_{uuid.uuid4().hex}{ext}")

    data = await asyncio.to_thread(download_twilio_media_sync, media_url)
    with open(filepath, "wb") as f:
        f.write(data)

    print(f"[WhatsApp] Image saved to {filepath}")
    return filepath