import asyncio
from xml.etree import ElementTree as ET



PHONE = "whatsapp:+9199999998947"
import services.whatsapp_service as ws  # 👈 ADD THIS
# 👇 MOCK HERE
async def mock_send_proactive_message(phone, message):
    print(f"\n📲 ALERT to {phone}:\n{message}\n")

ws.send_proactive_message = mock_send_proactive_message
from services.whatsapp_service import handle_incoming_message

def extract_message_text(twiml: str) -> str:
    try:
        root = ET.fromstring(twiml)
        msg = root.find("Message")
        return msg.text if msg is not None else twiml
    except Exception:
        return twiml


async def send_text(body: str):
    form_data = {
        "From": PHONE,
        "Body": body,
        "NumMedia": "0",
        "MediaUrl0": None,
        "MediaContentType0": None,
        "Latitude": None,
        "Longitude": None,
        "Address": None,
        "MessageSid": None,
    }
    twiml = await handle_incoming_message(form_data)
    print("\nBOT:\n" + extract_message_text(twiml) + "\n")


async def send_location(lat: str, lng: str):
    form_data = {
        "From": PHONE,
        "Body": "",
        "NumMedia": "0",
        "MediaUrl0": None,
        "MediaContentType0": None,
        "Latitude": lat,
        "Longitude": lng,
        "Address": None,
        "MessageSid": None,
    }
    twiml = await handle_incoming_message(form_data)
    print("\nBOT:\n" + extract_message_text(twiml) + "\n")


async def main():
    print("KrishiMitra terminal chat tester")
    print("Commands:")
    print("  /loc <lat> <lng>   -> simulate WhatsApp location share")
    print("  /exit              -> quit")
    print()

    while True:
        user = input("YOU: ").strip()
        if not user:
            continue
        if user.lower() == "/exit":
            break
        if user.lower().startswith("/loc "):
            parts = user.split()
            if len(parts) != 3:
                print("Use: /loc <lat> <lng>\n")
                continue
            await send_location(parts[1], parts[2])
            continue

        await send_text(user)


if __name__ == "__main__":
    asyncio.run(main())