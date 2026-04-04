import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import APIRouter, Request, Response
from twilio.twiml.messaging_response import MessagingResponse
from agent.scheduler import send_morning_briefings
from agent.agent import process_message, client as groq_client
from agent.diagnose import diagnose_image

# ✅ NEW: DB imports
from db.deps import get_db
from db.crud import upsert_farmer, add_crop, add_disease
from services.language_onboarding import maybe_handle_language_onboarding
from services.name_onboarding import maybe_handle_name_onboarding
from farmer_store import record_detection_if_outbreak, save_farmer_diagnosis

router = APIRouter()

_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_MODEL_SUB = "model" if os.path.isdir(os.path.join(_AGENT_DIR, "model")) else "models"
CLASSIFIER_PATH = os.path.join(_AGENT_DIR, _MODEL_SUB, "classifier.onnx")
DETECTOR_PATH = os.path.join(_AGENT_DIR, _MODEL_SUB, "detector.onnx")


# ─────────────────────────────────────────────────────────
# 📥 Download image from Twilio
# ─────────────────────────────────────────────────────────
def download_image(url: str) -> str:
    try:
        from services.twilio_media_download import download_twilio_media_sync

        print("📸 Media URL:", url)
        data = download_twilio_media_sync(url)
        img_path = os.path.join(os.path.dirname(__file__), "temp_image.jpg")
        with open(img_path, "wb") as f:
            f.write(data)
        print("✅ Image downloaded successfully")
        return img_path
    except Exception as e:
        print("❌ Download error:", e)
        return None


# ─────────────────────────────────────────────────────────
# 🧠 NEW: Extract structured farmer data
# ─────────────────────────────────────────────────────────
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
  "location": "city or null",
  "crop": "crop name or null",
  "disease": "disease or null",
  "language": "Hindi/English/Kannada"
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
        print(f"⚠️ Extraction failed: {e}")
        return {}


# ─────────────────────────────────────────────────────────
# 🧪 Test route
# ─────────────────────────────────────────────────────────
@router.get("/test-briefing")
async def test_briefing():
    await send_morning_briefings()
    return {"status": "Briefings sent ✅"}


# ─────────────────────────────────────────────────────────
# 📲 Main WhatsApp Webhook
# ─────────────────────────────────────────────────────────
@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()

    farmer_id = form.get("From", "")
    message = form.get("Body", "").strip()
    num_media = int(form.get("NumMedia", 0))
    media_url = form.get("MediaUrl0", "")

    print(f"\n📱 From: {farmer_id}")
    print(f"💬 Message: {message}")
    print(f"📸 Media: {num_media}")

    try:
        disease_result = None

        # ─────────────────────────────
        # 🌐 Language preference (text-only; before image/DB/agent)
        # ─────────────────────────────
        if num_media == 0:
            lang_reply = maybe_handle_language_onboarding(farmer_id, message)
            if lang_reply is not None:
                twiml = MessagingResponse()
                twiml.message(lang_reply)
                return Response(content=str(twiml), media_type="application/xml")

        if num_media == 0:
            name_reply = maybe_handle_name_onboarding(farmer_id, message)
            if name_reply is not None:
                twiml = MessagingResponse()
                twiml.message(name_reply)
                return Response(content=str(twiml), media_type="application/xml")

        # ─────────────────────────────
        # 📸 Image Handling (existing)
        # ─────────────────────────────
        if num_media > 0 and media_url:
            img_path = download_image(media_url)

            if img_path:
                disease_result = diagnose_image(
                    img_path, CLASSIFIER_PATH, DETECTOR_PATH
                )

                print(f"🦠 Disease: {disease_result['disease']}")
                print("🧪 Disease Result:", disease_result)
                save_farmer_diagnosis(farmer_id, disease_result, message)
                record_detection_if_outbreak(farmer_id, disease_result)
            if not message:
                message = "I sent a photo of my crop"

        # ─────────────────────────────
        # 💾 NEW: Auto-store in DB
        # ─────────────────────────────
        async for db in get_db():
            data = await extract_farmer_data(message)

            location = data.get("location")
            crop = data.get("crop")
            disease = data.get("disease")

            # Override disease if image detected
            if disease_result:
                disease = disease_result.get("disease")

            await upsert_farmer(db, farmer_id, location=location)

            if crop:
                await add_crop(db, farmer_id, crop)

            if disease:
                await add_disease(db, farmer_id, disease)

            print(f"💾 Stored for {farmer_id}")

        # ─────────────────────────────
        # 🤖 Existing Agent (unchanged)
        # ─────────────────────────────
        reply = await process_message(
            farmer_id=farmer_id,
            message=message if message else "Hello",
            disease_result=disease_result,
        )

        print(f"🤖 Reply: {reply[:100]}...")

    except Exception as e:
        print(f"❌ Error: {e}")
        reply = "Sorry, please try again."

    # ─────────────────────────────
    # 📤 Send reply (existing)
    # ─────────────────────────────
    twiml = MessagingResponse()
    twiml.message(reply)

    return Response(content=str(twiml), media_type="application/xml")


# ─────────────────────────────────────────────────────────
# 🧪 Health test
# ─────────────────────────────────────────────────────────
@router.get("/whatsapp/test")
def test_webhook():
    return {"status": "WhatsApp webhook running ✅"}
