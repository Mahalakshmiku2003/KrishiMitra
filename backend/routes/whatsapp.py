
from fastapi import APIRouter, Form
from fastapi.responses import Response
from services.whatsapp_service import handle_incoming_message

router = APIRouter()


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    From:                str = Form(...),
    Body:                str = Form(""),
    NumMedia:            str = Form("0"),
    MediaUrl0:           str = Form(None),
    MediaContentType0:   str = Form(None),
):
    """
    Twilio POSTs here every time a farmer sends a WhatsApp message.
    Must respond with TwiML XML within 15 seconds.
    Set this URL in Twilio sandbox: https://your-ngrok-url/webhook/whatsapp
    """
    form_data = {
        "From":              From,
        "Body":              Body,
        "NumMedia":          NumMedia,
        "MediaUrl0":         MediaUrl0,
        "MediaContentType0": MediaContentType0,
    }
    twiml_xml = await handle_incoming_message(form_data)
    return Response(content=twiml_xml, media_type="text/xml")