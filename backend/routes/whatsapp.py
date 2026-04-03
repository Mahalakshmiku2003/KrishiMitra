from fastapi import APIRouter, Form
from fastapi.responses import Response

from backend.services.whatsapp_service import handle_incoming_message

router = APIRouter()


@router.post("/whatsapp")
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(""),
    NumMedia: str = Form("0"),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
    Latitude: str = Form(None),
    Longitude: str = Form(None),
    Address: str = Form(None),
    MessageSid: str = Form(None),
):
    form_data = {
        "From": From,
        "Body": Body,
        "NumMedia": NumMedia,
        "MediaUrl0": MediaUrl0,
        "MediaContentType0": MediaContentType0,
        "Latitude": Latitude,
        "Longitude": Longitude,
        "Address": Address,
        "MessageSid": MessageSid,
    }
    twiml_xml = await handle_incoming_message(form_data)
    return Response(content=twiml_xml, media_type="application/xml; charset=utf-8")
