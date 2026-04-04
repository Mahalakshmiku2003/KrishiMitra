
from fastapi import APIRouter, Form
from fastapi.responses import Response
from services.whatsapp_service import handle_incoming_message

router = APIRouter()


# routes/whatsapp.py — add Latitude and Longitude to Form params
@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    From:              str = Form(...),
    Body:              str = Form(""),
    NumMedia:          str = Form("0"),
    MediaUrl0:         str = Form(None),
    MediaContentType0: str = Form(None),
    Latitude:          str = Form(None),   # NEW
    Longitude:         str = Form(None),   # NEW
    Address:           str = Form(None),   # NEW
):
    form_data = {
        "From": From, "Body": Body,
        "NumMedia": NumMedia,
        "MediaUrl0": MediaUrl0, "MediaContentType0": MediaContentType0,
        "Latitude": Latitude, "Longitude": Longitude, "Address": Address,
    }
    twiml_xml = await handle_incoming_message(form_data)
    return Response(
        content=twiml_xml.encode("utf-8"),
        media_type="application/xml; charset=utf-8",
    )