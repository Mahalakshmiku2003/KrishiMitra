from backend.scheduler import _send_followup

import asyncio


async def test():
    await _send_followup(
        phone="+911234567890", farmer_name="Test", disease_name="Blight", bbox_pct=40
    )


asyncio.run(test())
