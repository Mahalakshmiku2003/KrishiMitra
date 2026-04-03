import asyncio
from backend.scheduler import check_price_alerts

asyncio.run(check_price_alerts())
