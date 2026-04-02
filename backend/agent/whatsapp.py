import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import APIRouter, Request, Response
import requests as req
from twilio.twiml.messaging_response import MessagingResponse

from backend.agent.agent import (
    client as groq_client,
    process_message,
)
from backend.agent.diagnose import diagnose_image
from backend.agent.scheduler import send_morning_briefings
from backend.db.crud import (
    add_disease,
    _get_or_create_farmer,
    normalize,
    normalize_list,
)
from backend.db.database import AsyncSessionLocal

router = APIRouter()

_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_MODEL_SUB = "model" if os.path.isdir(os.path.join(_AGENT_DIR, "model")) else "models"
CLASSIFIER_PATH = os.path.join(_AGENT_DIR, _MODEL_SUB, "classifier.onnx")
DETECTOR_PATH = os.path.join(_AGENT_DIR, _MODEL_SUB, "detector.onnx")

# ── Language config ───────────────────────────────────────────────────────────

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

LANGUAGE_MAP = {
    "1": "Hindi",
    "2": "Kannada",
    "3": "English",
}

LANGUAGE_CONFIRM = {
    "Hindi": "✅ भाषा सेट हो गई: *हिंदी* 🌾\nअब अपना सवाल पूछें!",
    "Kannada": "✅ ಭಾಷೆ ಸೆಟ್ ಆಗಿದೆ: *ಕನ್ನಡ* 🌾\nಈಗ ನಿಮ್ಮ ಪ್ರಶ್ನೆ ಕೇಳಿ!",
    "English": "✅ Language set: *English* 🌾\nNow ask your question!",
}


# ── Helper ────────────────────────────────────────────────────────────────────


def _twiml_reply(text: str) -> Response:
    twiml = MessagingResponse()
    twiml.message(text)
    print("TWIML:", str(twiml))
    return Response(content=str(twiml), media_type="application/xml")


def download_image(url: str) -> str:
    try:
        sid = os.getenv("TWILIO_ACCOUNT_SID")
        token = os.getenv("TWILIO_AUTH_TOKEN")
        print("Media URL:", url)
        response = req.get(
            url, auth=(sid, token), headers={"User-Agent": "Mozilla/5.0"}, timeout=10
        )
        print(f"Download status: {response.status_code}")
        if response.status_code == 200:
            img_path = os.path.join(os.path.dirname(__file__), "temp_image.jpg")
            with open(img_path, "wb") as f:
                f.write(response.content)
            print("Image downloaded successfully")
            return img_path
        print("Failed with status:", response.status_code)
        return None
    except Exception as e:
        print("Download error:", e)
        return None


async def extract_farmer_data(message: str):
    try:
        response = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": """Extract farmer info.
Return ONLY JSON:
{
  "name": "person name or null",
  "location": "city or null",
  "crop": "crop name or null",
  "disease": "disease or null"
}""",
                },
                {"role": "user", "content": message},
            ],
            temperature=0.1,
        )
        import json, re

        raw = response.choices[0].message.content
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception as e:
        print(f"Extraction failed: {e}")
        return {}


@router.get("/test-briefing")
async def test_briefing():
    await send_morning_briefings()
    return {"status": "Briefings sent"}


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    print("STEP 1: Webhook received")
    form = await request.form()

    farmer_id = form.get("From", "")
    message = form.get("Body", "").strip()
    num_media = int(form.get("NumMedia", 0))
    media_url = form.get("MediaUrl0", "")
    print("FORM DATA:", dict(form))

    # ── Location share ────────────────────────────────────────────────────────
    lat = form.get("Latitude")
    lng = form.get("Longitude")

    if lat and lng:
        from backend.farmer_store import save_farmer_location
        from services.location_state import _pending_location

        save_farmer_location(farmer_id, float(lat), float(lng))
        print(f"[Location] Saved: {lat}, {lng} for {farmer_id}")

        pending = _pending_location.pop(farmer_id, None)
        if pending:
            from services.whatsapp_service import handle_location_for_mandi

            reply = await handle_location_for_mandi(
                phone=farmer_id,
                lat=float(lat),
                lng=float(lng),
                commodity=pending.get("commodity"),
            )
        else:
            reply = "Location saved! Ab aap mandi ya market ke baare mein pooch sakte hain. 📍🌾"
        return _twiml_reply(reply)

    print(f"From: {farmer_id}")
    print(f"Message: {message}")
    print(f"Media count: {num_media}")

    # ── Language selection flow (stateless — no in-memory dict needed) ────────
    db = AsyncSessionLocal()
    try:
        farmer, created = await _get_or_create_farmer(db, farmer_id)

        if farmer and not farmer.language:
            choice = message.strip()
            selected = LANGUAGE_MAP.get(choice)

            if not selected:
                # Not a valid choice (1/2/3) — show the menu
                # This handles: first visit, server restart, invalid input
                if created:
                    await db.commit()
                print(f"[Language] Showing menu to {farmer_id} (choice='{choice}')")
                return _twiml_reply(LANGUAGE_MENU)

            # Valid choice — save language and confirm
            farmer.language = selected
            await db.commit()
            await db.refresh(farmer)
            print(f"[Language] Saved '{selected}' for {farmer_id}")
            return _twiml_reply(LANGUAGE_CONFIRM[selected])

    except Exception as e:
        print(f"[Language] Error: {e}")
    finally:
        await db.close()

    # ── Normal message flow ───────────────────────────────────────────────────
    try:
        disease_result = None

        if num_media > 0 and media_url:
            img_path = download_image(media_url)
            if img_path:
                disease_result = diagnose_image(
                    img_path, CLASSIFIER_PATH, DETECTOR_PATH
                )
                print(f"Disease: {disease_result['disease']}")
                print("Disease Result:", disease_result)
            if not message:
                message = "I sent a photo of my crop"

        print("STEP 2: Before DB write")
        db = AsyncSessionLocal()
        try:
            data = await extract_farmer_data(message)
            name = normalize(data.get("name"))
            location = normalize(data.get("location"))
            crop = normalize(data.get("crop"))
            disease = normalize(data.get("disease"))

            if disease_result:
                disease = normalize(disease_result.get("disease"))

            farmer, created = await _get_or_create_farmer(db, farmer_id)
            farmer_language = farmer.language if farmer and farmer.language else "Hindi"

            if farmer:
                changed = created

                if location is not None and farmer.location != location:
                    farmer.location = location
                    changed = True

                if crop:
                    crops = normalize_list([*(farmer.crops or []), crop])
                    if crops != normalize_list(farmer.crops):
                        farmer.crops = crops
                        changed = True

                if changed:
                    if hasattr(farmer, "last_detection") and not isinstance(
                        farmer.last_detection, dict
                    ):
                        farmer.last_detection = {}
                    await db.commit()
                    await db.refresh(farmer)
                    print("DB updated once")
                    print("Farmer saved:", farmer.phone)

                if disease_result:
                    await add_disease(db, farmer_id, disease_result)
                elif disease:
                    await add_disease(
                        db,
                        farmer_id,
                        {"disease": disease, "severity": {"level": "unknown"}},
                    )

            print("DB updated successfully")
            print("STEP 2 DONE: DB updated")
        except Exception as e:
            print("DB ERROR:", e)
            raise
        finally:
            await db.close()

        print(f"STEP 3: Calling process_message (language={farmer_language})")
        try:
            reply = await process_message(
                farmer_id=farmer_id,
                message=message if message else "Hello",
                disease_result=disease_result,
                language=farmer_language,
            )
        except Exception as e:
            print("ERROR in process_message:", e)
            raise

        print(f"Reply: {reply[:100]}...")

    except Exception as e:
        print(f"Error: {e}")
        reply = "Sorry, please try again."

    print("STEP 7: Sending response to WhatsApp")
    return _twiml_reply(reply)


@router.get("/whatsapp/test")
def test_webhook():
    return {"status": "WhatsApp webhook running"}
