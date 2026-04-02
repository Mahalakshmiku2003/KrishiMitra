import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.db import models
from backend.db.database import Base, engine


async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('? All tables created!')


asyncio.run(init())
