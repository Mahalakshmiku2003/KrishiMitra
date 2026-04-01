"""
services/whatsapp_service.py
Handles all WhatsApp I/O via Twilio.
Receives messages, downloads images, calls the agent, sends reply.
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

load_dotenv()

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
FROM_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")  # whatsapp:+14155238886

twilio_client = Client(ACCOUNT_SID, AUTH_TOKEN)
TEMP_DIR = tempfile.gettempdir()
# ONNX weights live in backend/agent/model/ (singular)
AGENT_DIR = Path(__file__).resolve().parent.parent / "agent"
_MODEL_DIR = AGENT_DIR / "model"
if not (_MODEL_DIR / "classifier.onnx").exists():
    _MODEL_DIR = AGENT_DIR / "models"  # fallback if someone uses plural
CLASSIFIER_PATH = str(_MODEL_DIR / "classifier.onnx")
DETECTOR_PATH = str(_MODEL_DIR / "detector.onnx")


async def handle_incoming_message(form_data: dict) -> str:
    """
    Called by routes/whatsapp.py for every incoming WhatsApp message.
    Returns TwiML XML string — Twilio reads this and sends the reply.
    """
    phone = form_data.get("From", "").replace("whatsapp:", "").strip()
    body = form_data.get("Body", "").strip()
    num_media = int(form_data.get("NumMedia", 0))
    media_url = form_data.get("MediaUrl0")
    content_type = form_data.get("MediaContentType0")

    print(f"[WhatsApp] Message from {phone}: '{body}' | Media: {num_media}")

    image_path = None

    # Download image if farmer sent one
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

    msg_check = check_message(body)
    if not msg_check.allowed:
        twiml = MessagingResponse()
        twiml.message(msg_check.reply)
        return str(twiml)

    # Run working agent flow (backend/agent)
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

    # Clean up temp image file
    if image_path and os.path.exists(image_path):
        os.remove(image_path)

    # Build TwiML response
    twiml = MessagingResponse()
    twiml.message(reply)
    twiml_str = str(twiml)
    print(f"[DEBUG] Sending TwiML: {twiml_str}")  # add this
    return twiml_str


async def send_proactive_message(phone: str, message: str):
    """
    Send a WhatsApp message to a farmer without them initiating it.
    Use for: 3-day follow-ups, morning briefings, price alerts.
    """
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
    """Download image from Twilio CDN and save to temp folder."""
    ext_map = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    ext = ext_map.get(content_type, ".jpg")
    filepath = os.path.join(TEMP_DIR, f"kisan_{uuid.uuid4().hex}{ext}")

    import httpx

    auth = httpx.BasicAuth(ACCOUNT_SID, AUTH_TOKEN)

    async with httpx.AsyncClient(auth=auth) as client:
        response = await client.get(
            media_url,
            follow_redirects=True,
            timeout=30.0,
        )
        response.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(response.content)

    print(f"[WhatsApp] Image saved to {filepath}")
    return filepath
