import asyncio
from backend.services.whatsapp_service import handle_incoming_message


async def test():
    form_data = {
        "From": "whatsapp:+911234567890",
        "Body": "price of tomoto",
        "NumMedia": "0",
        "Latitude": "12.9716",
        "Longitude": "77.5946",
    }

    res = await handle_incoming_message(form_data)
    print("\nRESPONSE:\n", res)


asyncio.run(test())
