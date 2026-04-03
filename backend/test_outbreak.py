import asyncio
from outbreak.service import handle_new_detection


async def test():
    detection = {
        "phone": "+911234567890",
        "disease_name": "Late Blight",
        "crop_type": "tomato",
        "severity": 8,
        "lat": 12.97,
        "lng": 77.59,
        "spread": True,
    }

    await handle_new_detection(None, detection)


asyncio.run(test())
