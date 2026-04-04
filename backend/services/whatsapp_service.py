"""
services/whatsapp_service.py
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
from agent.diagnose import (
    diagnose_image_for_stated_crop,
    resolve_plantvillage_prefix,
)
from agent.guardrails import check_message, check_image
from services.location_state import _pending_location
from services.db import SessionLocal

from farmer_store import (
    get_farmer_language,
    get_farmer_location,
    save_farmer_location,
    record_detection_if_outbreak,
    save_disease_diagnosis_to_farmer,
)
from services.language_onboarding import maybe_handle_language_onboarding
from services.profile_onboarding import maybe_handle_name_onboarding
from services.disease_image_pending import (
    clear_pending_crop_image,
    peek_pending_crop_image,
    set_pending_crop_image,
    take_pending_crop_image,
)
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


def ask_which_crop_message(lang: str | None) -> str:
    l = (lang or "hindi").strip().lower()
    if l == "kannada":
        return (
            "ಫೋಟೋ ಸಿಕ್ಕಿತು. ದಯವಿಟ್ಟು *ಯಾವ ಬೆಳೆ* ಎಂದು ಸಂದೇಶದಲ್ಲಿ ಬರೆಯಿರಿ "
            "(ಉದಾ: tomato, potato, corn) — ನಂತರ ರೋಗ ತಪಾಸಣೆ ಮಾಡುತ್ತೇವೆ. 🌾"
        )
    if l == "english":
        return (
            "Photo received. Please reply with the *crop name* "
            "(e.g. tomato, potato, corn) so we can diagnose the disease. 🌾"
        )
    return (
        "Photo mil gaya. Kripya *kis fasal* ki photo hai yeh likh kar bhejein "
        "(jaise: tomato, potato, corn) — phir main bimari check karunga. 🌾"
    )


def disease_followup_scheduled_note(lang: str | None) -> str:
    l = (lang or "hindi").strip().lower()
    if l == "kannada":
        return (
            "\n\n*ಫಾಲೋ-ಅಪ್:* ನಾವು ಪ್ರತಿ *2 ದಿನಗಳಿಗೊಮ್ಮೆ* ನಿಮ್ಮ ಫಸಲಿನ ಆರೋಗ್ಯ "
            "ವಿಚಾರಿಸುತ್ತೇವೆ. 🌾"
        )
    if l == "english":
        return (
            "\n\n*Follow-up:* We will check on your crop health *every 2 days*. 🌾"
        )
    return (
        "\n\n*Follow-up:* Main aapki fasal ka haal *har 2 din* baad poochhunga. 🌾"
    )


def deliver_whatsapp_reply(form_data: dict, reply: str) -> str:
    """
    Send the bot reply with Twilio REST API (works reliably with async webhooks).
    Returns XML string for the HTTP response (empty <Response> when REST succeeds).
    """
    reply = (reply or "Sorry, please try again.").strip()
    if len(reply) > 4000:
        reply = reply[:3990] + "…"

    to_raw = (form_data.get("From") or "").strip()
    if not to_raw:
        twiml = MessagingResponse()
        twiml.message(reply)
        return str(twiml)

    if not to_raw.startswith("whatsapp:"):
        to_raw = f"whatsapp:{to_raw.replace('whatsapp:', '').strip()}"

    try:
        if not ACCOUNT_SID or not AUTH_TOKEN or not FROM_NUMBER:
            raise RuntimeError("Twilio credentials or FROM_NUMBER not set")
        twilio_client.messages.create(
            from_=FROM_NUMBER,
            to=to_raw,
            body=reply,
        )
        print(f"[WhatsApp] REST outbound reply sent → {to_raw}")
        return str(MessagingResponse())
    except Exception as e:
        print(f"[WhatsApp] REST send failed, TwiML fallback: {e}")
        twiml = MessagingResponse()
        twiml.message(reply)
        return str(twiml)


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
        reply = await handle_location_for_mandi(
            phone=phone,
            lat=float(latitude),
            lng=float(longitude),
            commodity=commodity,
            state_filter=None,
        )
        return deliver_whatsapp_reply(form_data, reply)

    # ── 2. Image message ─────────────────────────────────────────────────────
    image_path = None
    if num_media > 0 and media_url:
        img_check = check_image(content_type)
        if not img_check.allowed:
            return deliver_whatsapp_reply(form_data, img_check.reply)
        try:
            image_path = await _download_image(media_url, content_type)
        except Exception as e:
            print(f"[WhatsApp] Image download failed: {e}")

    # ── 3. Guardrail check ───────────────────────────────────────────────────
    msg_check = check_message(body)
    if not msg_check.allowed:
        return deliver_whatsapp_reply(form_data, msg_check.reply)

    # ── 3b. Language preference (first contact: hi/hello or 1/2/3) ───────────
    if num_media == 0:
        lang_reply = maybe_handle_language_onboarding(phone, body)
        if lang_reply is not None:
            return deliver_whatsapp_reply(form_data, lang_reply)

    # ── 3c. Name after language (pending capture) ───────────────────────────
    if num_media == 0:
        name_reply = maybe_handle_name_onboarding(phone, body)
        if name_reply is not None:
            return deliver_whatsapp_reply(form_data, name_reply)

    # ── 3d. Pending disease photo → farmer sends crop name ─────────────────
    disease_result = None
    if num_media == 0:
        if peek_pending_crop_image(phone):
            low = body.strip().lower()
            if low in ("cancel", "skip", "stop", "radd", "रद्द", "cancel karo"):
                clear_pending_crop_image(phone)
                return deliver_whatsapp_reply(
                    form_data,
                    "Theek hai, photo radd kar di. Zarurat ho to nayi photo bhejein. 🌾",
                )
            if not resolve_plantvillage_prefix(body):
                return deliver_whatsapp_reply(
                    form_data,
                    "Kripya sahi fasal ka naam bhejein: tomato, potato, corn, "
                    "pepper, grape, apple, cherry, strawberry, squash, soybean, "
                    "blueberry, orange, peach. 🌾",
                )
            img_p = take_pending_crop_image(phone)
            if not img_p or not os.path.isfile(img_p):
                return deliver_whatsapp_reply(
                    form_data,
                    "Photo purani ho gayi — kripya dubara photo bhejein. 🌾",
                )
            try:
                disease_result = diagnose_image_for_stated_crop(
                    img_p,
                    CLASSIFIER_PATH,
                    DETECTOR_PATH if os.path.exists(DETECTOR_PATH) else None,
                    body,
                )
            finally:
                if os.path.isfile(img_p):
                    try:
                        os.remove(img_p)
                    except OSError:
                        pass

    # ── 3e. New photo → ask crop first (no immediate full diagnosis) ─────────
    if num_media > 0 and image_path:
        if os.path.exists(CLASSIFIER_PATH):
            set_pending_crop_image(phone, image_path)
            return deliver_whatsapp_reply(
                form_data, ask_which_crop_message(get_farmer_language(phone))
            )
        print(f"[WhatsApp] Missing classifier at {CLASSIFIER_PATH}")
        try:
            os.remove(image_path)
        except OSError:
            pass

    followup_scheduled = False
    if disease_result:
        followup_scheduled = save_disease_diagnosis_to_farmer(
            phone, disease_result, body
        )
        record_detection_if_outbreak(phone, disease_result, body)

    # Optional ORM profile sync (Farmer / crops / diseases tables)
    farmer_id_orm = (form_data.get("From") or "").strip() or f"whatsapp:{phone}"
    try:
        from db.deps import get_db
        from db.crud import upsert_farmer, add_crop, add_disease
        from services.extract_farmer_llm import extract_farmer_data as llm_extract

        data = await llm_extract(body or "")
        loc = data.get("location")
        crop = data.get("crop")
        dis = data.get("disease")
        if disease_result:
            dis = disease_result.get("disease")
        async for db in get_db():
            await upsert_farmer(db, farmer_id_orm, location=loc)
            if crop:
                await add_crop(db, farmer_id_orm, crop)
            if dis:
                await add_disease(db, farmer_id_orm, dis)
    except Exception as e:
        print(f"[WhatsApp] ORM side-sync skipped: {e}")

    reply = await process_message(
        farmer_id=phone,
        message=body or "Hello",
        disease_result=disease_result,
    )

    if followup_scheduled:
        reply += disease_followup_scheduled_note(get_farmer_language(phone))

    print(f"[DEBUG] Agent reply length={len(reply)}")
    return deliver_whatsapp_reply(form_data, reply)


# services/whatsapp_service.py — replace handle_location_for_mandi entirely



async def handle_location_for_mandi(
    phone: str,
    lat: float,
    lng: float,
    commodity: str | None,
    state_filter: str | None = None,
    list_top_n: int = 3,
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
            top_n=max(3, min(list_top_n, 15)),
            db=db,
            state_filter=state_filter,
        )
    finally:
        db.close()

    if not results:
        return (
            f"*{commodity.title()}* ke liye 500km mein koi mandi nahi mili.\n"
            f"Pehle yeh run karein: POST /market/fetch\n\n"
            f"Koi aur madad chahiye? 🌾"
        )

    if list_top_n > 5:
        reply = (
            f"*{commodity.title()}* — *paas ke mandi (net price ke hisaab se):*\n\n"
        )
        for i, m in enumerate(results, 1):
            reply += (
                f"{i}. *{m['market']}* — {m['district']}, {m['state']}\n"
                f"   Modal: Rs.{m['modal_price']}/q | Doori: {m['distance_km']} km\n"
                f"   Transport ~Rs.{m['transport_cost']} | *Net ~Rs.{m['net_price']}/q*\n\n"
            )
        reply += "Koi aur madad chahiye? 🌾"
        return reply

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
    ext_map = {
        "image/jpeg": ".jpg",
        "image/jpg":  ".jpg",
        "image/png":  ".png",
        "image/webp": ".webp",
    }
    ext      = ext_map.get(content_type, ".jpg")
    filepath = os.path.join(TEMP_DIR, f"kisan_{uuid.uuid4().hex}{ext}")

    auth = httpx.BasicAuth(ACCOUNT_SID, AUTH_TOKEN)
    async with httpx.AsyncClient(auth=auth) as client:
        response = await client.get(media_url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(response.content)

    print(f"[WhatsApp] Image saved to {filepath}")
    return filepath