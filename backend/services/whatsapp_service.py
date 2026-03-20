import os
from twilio.rest import Client

TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

def _get_client():
    sid   = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        raise EnvironmentError("TWILIO credentials not set in .env")
    return Client(sid, token)

def send_text_message(to: str, body: str) -> str:
    to_wa  = f"whatsapp:{to}" if not to.startswith("whatsapp:") else to
    client = _get_client()
    msg    = client.messages.create(body=body, from_=TWILIO_WHATSAPP_NUMBER, to=to_wa)
    return msg.sid