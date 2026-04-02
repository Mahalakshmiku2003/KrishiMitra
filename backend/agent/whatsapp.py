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
  "disease": "disease or null",
  "language": "Hindi/English/Kannada"
}""",
                },
                {"role": "user", "content": message},
            ],
            temperature=0.1,
        )

        import json
        import re

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

    print(f"From: {farmer_id}")
    print(f"Message: {message}")
    print(f"Media count: {num_media}")

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
            language = normalize(data.get("language"))

            if disease_result:
                disease = normalize(disease_result.get("disease"))

            farmer, created = await _get_or_create_farmer(db, farmer_id)
            if farmer:
                changed = created
                
                if location is not None and farmer.location != location:
                    farmer.location = location
                    changed = True

                if language is not None:
                    farmer.language = language

                if crop:
                    crops = normalize_list([*(farmer.crops or []), crop])
                    if crops != normalize_list(farmer.crops):
                        farmer.crops = crops
                        changed = True

                if changed:
                    if hasattr(farmer, "last_detection") and not isinstance(
                        farmer.last_detection, dict
                    ):
                        print("FIXING last_detection before commit")
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

        print("STEP 3: Calling process_message")
        try:
            reply = await process_message(
                farmer_id=farmer_id,
                message=message if message else "Hello",
                disease_result=disease_result,
            )
        except Exception as e:
            print("ERROR in process_message:", e)
            raise

        print(f"Reply: {reply[:100]}...")

    except Exception as e:
        print(f"Error: {e}")
        reply = "Sorry, please try again."

    twiml = MessagingResponse()
    print("STEP 7: Sending response to WhatsApp")
    twiml.message(reply)
    print("RESPONSE SENT")

    return Response(content=str(twiml), media_type="application/xml")


@router.get("/whatsapp/test")
def test_webhook():
    return {"status": "WhatsApp webhook running"}
