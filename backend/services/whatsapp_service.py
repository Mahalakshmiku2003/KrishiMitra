"""
services/whatsapp_service.py
Handles all WhatsApp I/O via Twilio.
Receives messages, downloads images, calls the agent, sends reply.
"""

import os
import uuid
import httpx
import tempfile
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

from kisan_agent.agent import get_agent_response

load_dotenv()

ACCOUNT_SID   = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN")
FROM_NUMBER   = os.getenv("TWILIO_WHATSAPP_NUMBER")  # whatsapp:+14155238886

twilio_client = Client(ACCOUNT_SID, AUTH_TOKEN)
TEMP_DIR      = tempfile.gettempdir()


async def handle_incoming_message(form_data: dict) -> str:
    """
    Called by routes/whatsapp.py for every incoming WhatsApp message.
    Returns TwiML XML string — Twilio reads this and sends the reply.
    """
    phone        = form_data.get("From", "").replace("whatsapp:", "").strip()
    body         = form_data.get("Body", "").strip()
    num_media    = int(form_data.get("NumMedia", 0))
    media_url    = form_data.get("MediaUrl0")
    content_type = form_data.get("MediaContentType0")

    print(f"[WhatsApp] Message from {phone}: '{body}' | Media: {num_media}")

    image_path = None

    # Download image if farmer sent one
    if num_media > 0 and media_url:
        try:
            image_path = await _download_image(media_url, content_type)
        except Exception as e:
            print(f"[WhatsApp] Image download failed: {e}")

    # Get response from Kisan Agent
    reply = await get_agent_response(
        phone=phone,
        message=body,
        image_path=image_path,
        image_content_type=content_type,
    )

    # Clean up temp image file
    if image_path and os.path.exists(image_path):
        os.remove(image_path)

    # Build TwiML response
    twiml = MessagingResponse()
    twiml.message(reply)
    return str(twiml)


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
        "image/jpg":  ".jpg",
        "image/png":  ".png",
        "image/webp": ".webp",
    }
    ext      = ext_map.get(content_type, ".jpg")
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