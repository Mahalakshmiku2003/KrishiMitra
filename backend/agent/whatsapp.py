import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import APIRouter, Request, Response

from agent.scheduler import send_morning_briefings
from services.whatsapp_service import handle_incoming_message

router = APIRouter()


@router.get("/test-briefing")
async def test_briefing():
    await send_morning_briefings()
    return {"status": "Briefings sent ✅"}


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Twilio webhook — same pipeline as /webhook/whatsapp (REST outbound + UTF-8 XML).
    """
    form = await request.form()
    fd = dict(form)
    fd["Body"] = fd.get("Body") or ""
    fd["NumMedia"] = str(fd.get("NumMedia") if fd.get("NumMedia") is not None else "0")
    fd["From"] = fd.get("From") or ""

    xml = await handle_incoming_message(fd)
    return Response(
        content=xml.encode("utf-8"),
        media_type="application/xml; charset=utf-8",
    )


@router.get("/whatsapp/test")
def test_webhook():
    return {"status": "WhatsApp webhook running ✅"}
