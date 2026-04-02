"""
services/whatsapp_service.py

Fixes applied:
  - [BUG] handle_incoming_message was defined twice in this file. The second
    definition silently overwrote the first at import time, so the first
    version's logic (including the "location saved" confirmation branch) was
    never reachable. The second definition is now the sole version — it is
    the more complete one and matches the behavior the active handler in
    backend/agent/whatsapp.py expects when it imports handle_location_for_mandi.
  - No logic changes to handle_location_for_mandi or any other function.
"""

import os
import uuid
import httpx
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
from backend.farmer_store import get_farmer_location, save_farmer_location
from services.market_service import (
    find_nearest_from_json,
    find_best_mandi_for_commodity,
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


async def handle_incoming_message(form_data: dict) -> str:
    """Single handler: location check first, then normal agent flow."""
    print(f"[DEBUG] Full form_data: {form_data}")

    phone = form_data.get("From", "").replace("whatsapp:", "").strip()
    body = form_data.get("Body", "").strip()
    num_media = int(form_data.get("NumMedia", 0))
    media_url = form_data.get("MediaUrl0")
    content_type = form_data.get("MediaContentType0")
    latitude = form_data.get("Latitude")
    longitude = form_data.get("Longitude")

    print(
        f"[DEBUG] lat={latitude}, lng={longitude}, pending={phone in _pending_location}"
    )

    # ── 1. Location message ───────────────────────────────────────────────────
    if latitude and longitude:
        lat = float(latitude)
        lng = float(longitude)

        save_farmer_location(phone, lat, lng)
        print(f"[Location] Saved: {lat}, {lng} for {phone}")

        pending = _pending_location.pop(phone, None)
        if pending:
            reply = await handle_location_for_mandi(
                phone=phone,
                lat=lat,
                lng=lng,
                commodity=pending.get("commodity"),
            )
            twiml = MessagingResponse()
            twiml.message(reply)
            return str(twiml)

        twiml = MessagingResponse()
        twiml.message(
            "Location saved! Ab aap mandi ya market ke baare mein pooch sakte hain. 📍🌾"
        )
        return str(twiml)

    # ── 2. Image message ──────────────────────────────────────────────────────
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

    # ── 3. Guardrail check ────────────────────────────────────────────────────
    msg_check = check_message(body)
    if not msg_check.allowed:
        twiml = MessagingResponse()
        twiml.message(msg_check.reply)
        return str(twiml)

    # ── 4. Normal agent flow ──────────────────────────────────────────────────
    disease_result = None
    if image_path and os.path.exists(CLASSIFIER_PATH):
        disease_result = diagnose_image(
            image_path=image_path,
            classifier_path=CLASSIFIER_PATH,
            detector_path=DETECTOR_PATH if os.path.exists(DETECTOR_PATH) else None,
        )
    elif image_path:
        print(f"[WhatsApp] Missing classifier at {CLASSIFIER_PATH}")

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


async def handle_location_for_mandi(
    phone: str, lat: float, lng: float, commodity: str | None
) -> str:

    # ── Flow B: no commodity — nearest mandis from JSON ──────────────────────
    if not commodity:
        nearest = find_nearest_from_json(lat, lng, top_n=5)
        if not nearest:
            return "Aapke paas koi mandi nahi mili.\n\nKoi aur madad chahiye? 🌾"

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
        )
    finally:
        db.close()

    if not results:
        return (
            f"*{commodity.title()}* ke liye 500km mein koi mandi nahi mili.\n"
            f"Pehle yeh run karein: POST /market/fetch\n\n"
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
            reply += (
                f"  • {m['market']} — Rs.{m['net_price']}/q ({m['distance_km']}km)\n"
            )

    reply += "\nKoi aur madad chahiye? 🌾"
    return reply


async def send_proactive_message(phone: str, message: str):
    message = message[:1599]
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

    print(f"[WhatsApp] Image saved to {filepath}")
    return filepath
