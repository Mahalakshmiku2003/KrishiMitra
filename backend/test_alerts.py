import asyncio
from backend.scheduler import check_price_alerts
import asyncio

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(check_price_alerts())
