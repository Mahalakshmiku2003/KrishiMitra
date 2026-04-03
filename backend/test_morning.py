import asyncio
from backend.scheduler import morning_briefing
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
asyncio.run(morning_briefing())
