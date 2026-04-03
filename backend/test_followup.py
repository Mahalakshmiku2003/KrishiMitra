import asyncio
from backend.scheduler import _send_followup
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


async def test():
    await _send_followup(
        phone="+917411272713", farmer_name="Test", disease_name="blight", bbox_pct=40
    )


asyncio.run(test())
